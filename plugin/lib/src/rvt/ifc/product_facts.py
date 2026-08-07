"""rvt.ifc.product_facts -- extract a PRODUCT-FACTS record from an IFC product.

Turns ONE IFC element (an ``IfcLightFixture`` / any ``IfcElement`` with a
tessellated body) into the FACTS that drive one of OUR generated Revit
families.  Nothing here authors geometry -- it MEASURES the IFC we authored:

* IDENTITY   -- entity class, Name / Description / Tag / PredefinedType,
                GlobalId, containing storey, placement (identity or not).
* PSETS      -- every ``IfcPropertySet`` attached by
                ``IfcRelDefinesByProperties``, each property as a TYPED value
                (``IfcLabel`` -> str, ``IfcReal`` / ``IfcLengthMeasure`` ->
                float, ``IfcInteger`` -> int, ``IfcBoolean`` -> bool), the
                IFC measure type kept alongside.
* GEOMETRY   -- the body representation's tessellated meshes
                (``IfcTriangulatedFaceSet``): the OVERALL bounding box and a
                bounding box PER MESH (each mesh is one named sub-part via
                its ``IfcStyledItem``), in the product's OWN local frame,
                converted metres -> feet (Revit internal) and inches (the
                catalog convention).  Vertex / face counts per mesh.
* STYLES     -- the ``IfcSurfaceStyle`` colours (name -> sRGB triple) and
                which sub-parts wear each style.

The output is a facts RECORD in the ``rvt.famgen.catalog`` facts-store
schema (``docs/writer/facts-store.md`` §2): one ``variants[]`` entry (the
product), ``line_facts`` for the line-level geometry / photometry policy,
per-field provenance flags.  PROVENANCE POLICY: the IFC file is OUR OWN
document (Claude-Design / three-d-stage IFC writer), read this session by
this module -- every value taken FROM the file is a ``fact`` whose source is
the file itself (``sources.S1`` = the IFC path + its sha256, verification
``VERIFIED``); values the file does NOT state (wattage, lumens, colour
temperature, input voltage -- this IFC carries no electrical pset) are
``null`` = NOT SOURCED and are NEVER invented; the family constructor
surfaces them as unset parameters.  The record self-validates with
``rvt.famgen.catalog.validate_line`` (schema + provenance rules).

Public API::

    from rvt.ifc import product_facts as PF
    facts = PF.extract_product_facts("inputs/ifc/chicago-plenum-downlight.ifc")
    facts.psets["ChicagoPlenumSpecification"]["Rating"]["value"]
    facts.overall_dims_ft            # {'x': ..., 'y': ..., 'z': ...} feet
    facts.part("housing_can").dims_ft
    rec = PF.to_facts_record(facts)  # catalog facts-store schema (dict)
    PF.write_facts_record(facts, "experiments/families/ifc/x.facts.json")

CLI::

    python -m rvt.ifc.product_facts [IFC] [-o OUT.json] [--json]

TERRITORY: this module + ``tests/test_ifc_family.py`` +
``experiments/families/ifc/**`` (the IFC-family workstream).  Reads
``inputs/ifc/*.ifc``; imports ``ifcopenshell`` (installed, ``tools/
ifc_to_spec.py`` precedent) and ``rvt.famgen.catalog`` (validation only);
edits no other module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field as dc_field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))

#: the flagship IFC input (OUR IFC4 of the Chicago-plenum recessed downlight)
DEFAULT_IFC = os.path.join(_ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
#: default facts-record output path (this workstream's territory)
DEFAULT_FACTS_JSON = os.path.join(_ROOT, "experiments", "families", "ifc",
                                  "chicago_plenum_downlight.facts.json")

FT_PER_M = 1.0 / 0.3048
IN_PER_M = FT_PER_M * 12.0
MM_PER_M = 1000.0


class ProductFactsError(ValueError):
    """The IFC has no usable product / geometry, or ifcopenshell is missing."""


# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------

@dataclass
class MeshPart:
    """ONE tessellated mesh of the product's body = one named sub-part.

    ``name`` is the ``IfcStyledItem`` name the exporter gave the mesh (e.g.
    ``'housing_can'``, ``'trim_reflector'``); ``role`` is OUR functional
    classification of that name (:func:`classify_part`).  Bounding boxes are
    in the product's own LOCAL frame (the representation coordinate system --
    no world placement applied), metres and feet.
    """
    name: str
    role: str
    style: Optional[str]
    colour: Optional[Tuple[float, float, float]]
    n_points: int
    n_faces: int
    bbox_m: List[List[float]]                 # [[minx,miny,minz],[maxx,maxy,maxz]]
    bbox_ft: List[List[float]]
    dims_m: Dict[str, float]                  # {'x','y','z'} extents (metres)
    dims_ft: Dict[str, float]
    dims_in: Dict[str, float]

    def center_m(self) -> List[float]:
        return [round((self.bbox_m[0][i] + self.bbox_m[1][i]) / 2.0, 6) for i in range(3)]

    def center_ft(self) -> List[float]:
        return [c * FT_PER_M for c in self.center_m()]

    def to_json(self) -> dict:
        d = asdict(self)
        d["center_m"] = self.center_m()
        return d


@dataclass
class ProductFacts:
    """Every fact extracted from ONE IFC product (see module docstring)."""
    source_path: str
    source_sha256: str
    source_bytes: int
    schema: str
    project_name: str
    application: str                       # the authoring app named in the header
    unit_scale_m: float                    # metres per model length unit
    product: Dict[str, Any]                # class / name / description / tag / guid / ...
    placement: Dict[str, Any]              # storey, elevation, identity flag, matrix
    psets: Dict[str, Dict[str, Dict[str, Any]]]   # pset -> prop -> {value, ifc_type}
    parts: List[MeshPart]
    surface_styles: Dict[str, Dict[str, Any]]     # style name -> {rgb, transparency, parts}
    overall_bbox_m: List[List[float]]
    overall_bbox_ft: List[List[float]]
    overall_dims_m: Dict[str, float]
    overall_dims_ft: Dict[str, float]
    overall_dims_in: Dict[str, float]
    counts: Dict[str, int]
    extracted_at: str = ""
    notes: List[str] = dc_field(default_factory=list)

    # -- convenience -------------------------------------------------------
    def part(self, name: str) -> MeshPart:
        for p in self.parts:
            if p.name == name:
                return p
        raise KeyError(f"no mesh part named {name!r} (have {[p.name for p in self.parts]})")

    def parts_by_role(self, role: str) -> List[MeshPart]:
        return [p for p in self.parts if p.role == role]

    def pset_value(self, prop: str, pset: Optional[str] = None, default: Any = None) -> Any:
        """The typed value of a property (searched across all psets unless
        ``pset`` names one).  ``default`` when absent."""
        for pname, props in self.psets.items():
            if pset is not None and pname != pset:
                continue
            if prop in props:
                return props[prop]["value"]
        return default

    def to_json(self) -> dict:
        return {
            "source_path": self.source_path, "source_sha256": self.source_sha256,
            "source_bytes": self.source_bytes, "schema": self.schema,
            "project_name": self.project_name, "application": self.application,
            "unit_scale_m": self.unit_scale_m, "product": self.product,
            "placement": self.placement, "psets": self.psets,
            "parts": [p.to_json() for p in self.parts],
            "surface_styles": self.surface_styles,
            "overall_bbox_m": self.overall_bbox_m, "overall_bbox_ft": self.overall_bbox_ft,
            "overall_dims_m": self.overall_dims_m, "overall_dims_ft": self.overall_dims_ft,
            "overall_dims_in": self.overall_dims_in, "counts": self.counts,
            "extracted_at": self.extracted_at, "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _r(x: float, nd: int = 6) -> float:
    return round(float(x), nd)


def _bbox_of(points: Iterable[Sequence[float]]) -> Tuple[List[float], List[float]]:
    it = iter(points)
    try:
        p0 = next(it)
    except StopIteration:
        raise ProductFactsError("mesh has no points")
    mn = [float(p0[0]), float(p0[1]), float(p0[2])]
    mx = list(mn)
    for p in it:
        for i in range(3):
            v = float(p[i])
            if v < mn[i]:
                mn[i] = v
            if v > mx[i]:
                mx[i] = v
    return mn, mx


def _dims(mn: Sequence[float], mx: Sequence[float]) -> Dict[str, float]:
    return {"x": _r(mx[0] - mn[0]), "y": _r(mx[1] - mn[1]), "z": _r(mx[2] - mn[2])}


def _scale_bbox(bb: List[List[float]], k: float) -> List[List[float]]:
    return [[_r(v * k) for v in bb[0]], [_r(v * k) for v in bb[1]]]


def _scale_dims(d: Dict[str, float], k: float) -> Dict[str, float]:
    return {a: _r(v * k) for a, v in d.items()}


#: OUR functional classification of the exporter's part names (name substring
#: -> role).  The five colour-styled clusters of the flagship downlight are
#: housing (frame + boxes + hangers, galvanized_steel), can (housing_can /
#: gasket, gunmetal_steel), trim (white_enamel), lens (frosted_lens) and
#: hardware (zinc_hardware); the roles below refine that per part.
_ROLE_RULES: Tuple[Tuple[str, str], ...] = (
    ("housing_can", "can"),
    ("trim", "trim"),
    ("lens", "lens"),
    ("plaster_frame", "frame"),
    ("frame_lip", "frame"),
    ("hanger_bar", "hanger"),
    ("nail_flag", "hanger"),
    ("junction_box", "junction_box"),
    ("jbox", "junction_box"),
    ("driver_box", "driver_box"),
    ("knockout", "hardware"),
    ("screw", "hardware"),
    ("locknut", "hardware"),
    ("conduit", "hardware"),
    ("gasket", "hardware"),
)


def classify_part(name: str) -> str:
    """Map an exporter mesh name to OUR functional role
    ('can' | 'trim' | 'lens' | 'frame' | 'hanger' | 'junction_box' |
    'driver_box' | 'hardware' | 'other').  Rule = first substring match in
    :data:`_ROLE_RULES` (so 'jbox_gasket' is 'junction_box'-family before
    'gasket'-hardware)."""
    n = str(name or "").lower()
    for key, role in _ROLE_RULES:
        if key in n:
            return role
    return "other"


_MEASURE_FLOAT = ("IfcReal", "IfcLengthMeasure", "IfcPositiveLengthMeasure",
                  "IfcAreaMeasure", "IfcVolumeMeasure", "IfcPowerMeasure",
                  "IfcElectricVoltageMeasure", "IfcElectricCurrentMeasure",
                  "IfcLuminousFluxMeasure", "IfcThermodynamicTemperatureMeasure",
                  "IfcNumericMeasure", "IfcRatioMeasure", "IfcMassMeasure",
                  "IfcPlaneAngleMeasure", "IfcFrequencyMeasure",
                  "IfcNormalisedRatioMeasure", "IfcTimeMeasure")
_MEASURE_INT = ("IfcInteger", "IfcCountMeasure")
_MEASURE_BOOL = ("IfcBoolean", "IfcLogical")


def _typed_value(nominal: Any) -> Tuple[Any, str]:
    """(python value, IFC measure type name) of an IfcValue wrapper."""
    if nominal is None:
        return None, ""
    try:
        typ = str(nominal.is_a())
        raw = nominal.wrappedValue
    except Exception:                                          # a plain value
        return nominal, type(nominal).__name__
    if typ in _MEASURE_FLOAT:
        try:
            return float(raw), typ
        except (TypeError, ValueError):
            return raw, typ
    if typ in _MEASURE_INT:
        try:
            return int(raw), typ
        except (TypeError, ValueError):
            return raw, typ
    if typ in _MEASURE_BOOL:
        if isinstance(raw, str):
            return raw.upper() in ("T", "TRUE", ".T."), typ
        return bool(raw), typ
    return (raw if not isinstance(raw, bytes) else raw.decode("utf-8", "replace")), typ


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

def _open_ifc(path: str):
    try:
        import ifcopenshell as _i
    except Exception as e:                        # pragma: no cover
        raise ProductFactsError(f"ifcopenshell not importable: {e}")
    return _i.open(path)


def _pick_product(f, product_class: Optional[str], product_guid: Optional[str]):
    """The one product to extract: by GlobalId, by class, else the single
    element with a body representation (IfcLightFixture preferred)."""
    if product_guid:
        p = f.by_guid(product_guid)
        if p is None:
            raise ProductFactsError(f"no entity with GlobalId {product_guid}")
        return p
    if product_class:
        hits = list(f.by_type(product_class))
        if not hits:
            raise ProductFactsError(f"no {product_class} in the file")
        if len(hits) > 1:
            raise ProductFactsError(f"{len(hits)} {product_class} products -- name one by "
                                    f"GlobalId (product_guid=)")
        return hits[0]
    for cls in ("IfcLightFixture", "IfcElement"):
        hits = [e for e in f.by_type(cls) if getattr(e, "Representation", None) is not None]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ProductFactsError(f"{len(hits)} products with geometry -- name one "
                                    f"(product_class= / product_guid=)")
    raise ProductFactsError("no product with a body representation found")


def _storey_of(product) -> Tuple[str, Optional[float]]:
    for rel in getattr(product, "ContainedInStructure", ()) or ():
        st = rel.RelatingStructure
        if st is not None and st.is_a("IfcBuildingStorey"):
            elev = getattr(st, "Elevation", None)
            return str(st.Name or ""), (float(elev) if elev is not None else None)
    return "", None


def _placement_matrix(product):
    """4x4 local->world matrix (identity if unresolvable)."""
    try:
        import ifcopenshell.util.placement as upl
        m = upl.get_local_placement(product.ObjectPlacement)
        return [[float(m[r][c]) for c in range(4)] for r in range(4)]
    except Exception:
        return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def _is_identity(m: List[List[float]], eps: float = 1e-9) -> bool:
    for r in range(4):
        for c in range(4):
            want = 1.0 if r == c else 0.0
            if abs(float(m[r][c]) - want) > eps:
                return False
    return True


def _collect_psets(product) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """{pset_name: {prop_name: {'value', 'ifc_type', 'wrapped'}}} over
    IfcRelDefinesByProperties (single-value properties; quantities as
    values of their measure)."""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rel in getattr(product, "IsDefinedBy", ()) or ():
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pdef = rel.RelatingPropertyDefinition
        if pdef is None:
            continue
        pname = str(getattr(pdef, "Name", "") or "Pset")
        props: Dict[str, Dict[str, Any]] = out.setdefault(pname, {})
        if pdef.is_a("IfcPropertySet"):
            for pr in pdef.HasProperties or ():
                if pr.is_a("IfcPropertySingleValue"):
                    val, typ = _typed_value(pr.NominalValue)
                    props[str(pr.Name)] = {"value": val, "ifc_type": typ}
                elif pr.is_a("IfcPropertyEnumeratedValue"):
                    vals = [_typed_value(v)[0] for v in (pr.EnumerationValues or ())]
                    props[str(pr.Name)] = {"value": (vals[0] if len(vals) == 1 else vals),
                                            "ifc_type": "IfcPropertyEnumeratedValue"}
                elif pr.is_a("IfcPropertyListValue"):
                    vals = [_typed_value(v)[0] for v in (pr.ListValues or ())]
                    props[str(pr.Name)] = {"value": vals, "ifc_type": "IfcPropertyListValue"}
        elif pdef.is_a("IfcElementQuantity"):
            for q in pdef.Quantities or ():
                for attr in ("LengthValue", "AreaValue", "VolumeValue", "CountValue",
                             "WeightValue", "TimeValue"):
                    if hasattr(q, attr) and getattr(q, attr) is not None:
                        props[str(q.Name)] = {"value": float(getattr(q, attr)),
                                               "ifc_type": q.is_a()}
                        break
    return out


def _styled_index(f) -> Dict[int, Any]:
    """representation item id -> its IfcStyledItem."""
    idx: Dict[int, Any] = {}
    for si in f.by_type("IfcStyledItem"):
        it = getattr(si, "Item", None)
        if it is not None:
            idx[it.id()] = si
    return idx


def _style_of(styled_item) -> Tuple[Optional[str], Optional[Tuple[float, float, float]], Optional[float]]:
    """(surface style name, (r,g,b), transparency) of a styled item."""
    if styled_item is None:
        return None, None, None
    for assign in getattr(styled_item, "Styles", ()) or ():
        # IFC4: Styles is a list of IfcPresentationStyleAssignment (with .Styles)
        # or IfcSurfaceStyle directly (IFC4 ADD1+); handle both.
        candidates = []
        if assign.is_a("IfcSurfaceStyle"):
            candidates = [assign]
        else:
            candidates = [s for s in (getattr(assign, "Styles", ()) or ())
                          if s.is_a("IfcSurfaceStyle")]
        for st in candidates:
            rgb, transp = None, None
            for s2 in st.Styles or ():
                if s2.is_a("IfcSurfaceStyleRendering") or s2.is_a("IfcSurfaceStyleShading"):
                    c = s2.SurfaceColour
                    if c is not None:
                        rgb = (_r(c.Red, 6), _r(c.Green, 6), _r(c.Blue, 6))
                    transp = getattr(s2, "Transparency", None)
                    transp = float(transp) if transp is not None else None
            return (str(st.Name) if st.Name else None), rgb, transp
    return None, None, None


def _mesh_points(item) -> List[Sequence[float]]:
    """The vertex list of a tessellated body item (IfcTriangulatedFaceSet /
    IfcPolygonalFaceSet)."""
    coords = getattr(item, "Coordinates", None)
    if coords is None:
        raise ProductFactsError(f"item #{item.id()} {item.is_a()} has no Coordinates "
                                f"(only tessellated bodies are measured)")
    return list(coords.CoordList)


def _mesh_face_count(item) -> int:
    if hasattr(item, "CoordIndex") and item.CoordIndex is not None:
        return len(item.CoordIndex)
    if hasattr(item, "Faces") and item.Faces is not None:
        return len(item.Faces)
    return 0


def extract_product_facts(ifc_path: str = DEFAULT_IFC, *,
                          product_class: Optional[str] = None,
                          product_guid: Optional[str] = None,
                          representation_identifier: str = "Body") -> ProductFacts:
    """Extract the :class:`ProductFacts` of one IFC product.

    ``product_class`` / ``product_guid`` select the product (default: the
    single ``IfcLightFixture`` / element with a body).  Geometry is measured
    from the ``representation_identifier`` ('Body') representation's
    tessellated meshes in the product's own local frame; the world placement
    is recorded separately (identity for our exporter's fixtures).
    """
    path = os.path.abspath(ifc_path)
    if not os.path.isfile(path):
        raise ProductFactsError(f"IFC not found: {path}")
    f = _open_ifc(path)
    schema = str(getattr(f, "schema", "") or "")
    # header application (the authoring app -- ours)
    application = ""
    try:
        application = str(f.wrapped_data.header.file_name.originating_system or "")
    except Exception:
        try:
            apps = f.by_type("IfcApplication")
            application = str(apps[0].ApplicationFullName) if apps else ""
        except Exception:
            application = ""
    proj = (f.by_type("IfcProject") or [None])[0]
    project_name = str(proj.Name) if (proj is not None and proj.Name) else ""
    try:
        import ifcopenshell.util.unit as uu
        scale = float(uu.calculate_unit_scale(f))
    except Exception:
        scale = 1.0
    prod = _pick_product(f, product_class, product_guid)
    storey, storey_elev = _storey_of(prod)
    pmatrix = _placement_matrix(prod)

    # -- geometry: the Body representation's tessellated meshes ----------------
    reps = []
    pdef = getattr(prod, "Representation", None)
    if pdef is not None:
        reps = [r for r in (pdef.Representations or ())
                if str(getattr(r, "RepresentationIdentifier", "") or "") == representation_identifier]
        if not reps:                       # fall back to any representation
            reps = list(pdef.Representations or ())
    if not reps:
        raise ProductFactsError("product has no body representation")
    items = []
    rep_types = set()
    for r in reps:
        rep_types.add(str(getattr(r, "RepresentationType", "") or ""))
        for it in (r.Items or ()):
            # unwrap mapped items one level (IfcMappedItem -> its source items)
            if it.is_a("IfcMappedItem"):
                src = it.MappingSource.MappedRepresentation
                items.extend(list(src.Items or ()))
            else:
                items.append(it)
    tess = [it for it in items if it.is_a("IfcTessellatedFaceSet")
            or it.is_a("IfcTriangulatedFaceSet") or it.is_a("IfcPolygonalFaceSet")]
    if not tess:
        raise ProductFactsError(
            f"no tessellated meshes in the body (item types: "
            f"{sorted({it.is_a() for it in items})}); this extractor measures "
            f"IfcTriangulatedFaceSet bodies (the three-d-stage IFC writer's output)")
    styled = _styled_index(f)
    parts: List[MeshPart] = []
    all_mn: List[float] = [float("inf")] * 3
    all_mx: List[float] = [float("-inf")] * 3
    styles: Dict[str, Dict[str, Any]] = {}
    total_pts = total_faces = 0
    unnamed = 0
    for it in tess:
        pts = _mesh_points(it)
        nfaces = _mesh_face_count(it)
        mn, mx = _bbox_of(pts)
        si = styled.get(it.id())
        sname, rgb, transp = _style_of(si)
        pname = str(si.Name) if (si is not None and si.Name) else ""
        if not pname:
            unnamed += 1
            pname = f"mesh_{it.id()}"
        # metres (scaled) in the product's LOCAL frame
        mn_m = [v * scale for v in mn]
        mx_m = [v * scale for v in mx]
        for i in range(3):
            all_mn[i] = min(all_mn[i], mn_m[i])
            all_mx[i] = max(all_mx[i], mx_m[i])
        bbox_m = [[_r(v) for v in mn_m], [_r(v) for v in mx_m]]
        dims_m = _dims(mn_m, mx_m)
        part = MeshPart(
            name=pname, role=classify_part(pname), style=sname, colour=rgb,
            n_points=len(pts), n_faces=int(nfaces),
            bbox_m=bbox_m, bbox_ft=_scale_bbox(bbox_m, FT_PER_M),
            dims_m=dims_m, dims_ft=_scale_dims(dims_m, FT_PER_M),
            dims_in=_scale_dims(dims_m, IN_PER_M))
        parts.append(part)
        total_pts += part.n_points
        total_faces += part.n_faces
        if sname:
            ent = styles.setdefault(sname, {"rgb": rgb, "transparency": transp, "parts": []})
            ent["parts"].append(pname)
    overall_bbox_m = [[_r(v) for v in all_mn], [_r(v) for v in all_mx]]
    overall_dims_m = _dims(all_mn, all_mx)

    prod_info = {
        "ifc_class": str(prod.is_a()),
        "name": str(prod.Name or ""),
        "description": str(getattr(prod, "Description", "") or ""),
        "tag": str(getattr(prod, "Tag", "") or ""),
        "predefined_type": str(getattr(prod, "PredefinedType", "") or ""),
        "object_type": str(getattr(prod, "ObjectType", "") or ""),
        "global_id": str(getattr(prod, "GlobalId", "") or ""),
    }
    placement = {
        "storey": storey, "storey_elevation_m": storey_elev,
        "matrix": pmatrix, "is_identity": _is_identity(pmatrix),
        "coords": "product LOCAL frame (representation CS); world = matrix @ local",
    }
    facts = ProductFacts(
        source_path=path, source_sha256=_sha256(path), source_bytes=os.path.getsize(path),
        schema=schema, project_name=project_name, application=application,
        unit_scale_m=scale, product=prod_info, placement=placement,
        psets=_collect_psets(prod), parts=parts, surface_styles=styles,
        overall_bbox_m=overall_bbox_m,
        overall_bbox_ft=_scale_bbox(overall_bbox_m, FT_PER_M),
        overall_dims_m=overall_dims_m,
        overall_dims_ft=_scale_dims(overall_dims_m, FT_PER_M),
        overall_dims_in=_scale_dims(overall_dims_m, IN_PER_M),
        counts={"meshes": len(parts), "points": total_pts, "faces": total_faces,
                "surface_styles": len(styles), "psets": 0, "properties": 0,
                "unnamed_meshes": unnamed},
        extracted_at=time.strftime("%Y-%m-%d"),
    )
    facts.counts["psets"] = len(facts.psets)
    facts.counts["properties"] = sum(len(v) for v in facts.psets.values())
    if rep_types:
        facts.notes.append(f"body representation type(s): {sorted(rep_types)}")
    if not placement["is_identity"]:
        facts.notes.append("world placement is NOT identity -- bboxes are the product-local "
                           "frame; apply placement.matrix for world coordinates")
    if unnamed:
        facts.notes.append(f"{unnamed} mesh(es) had no IfcStyledItem name (named mesh_<id>)")
    return facts


# ---------------------------------------------------------------------------
# derived downlight geometry (the housing / can / trim / aperture facts)
# ---------------------------------------------------------------------------

def _parse_aperture_label(label: str) -> Dict[str, Optional[float]]:
    """'6 in (152 mm) round' -> {'in': 6.0, 'mm': 152.0}; missing -> None.
    The values are exactly what the label STATES (152 mm, not 152.4)."""
    out: Dict[str, Optional[float]] = {"in": None, "mm": None}
    if not label:
        return out
    m = re.search(r"(\d+(?:\.\d+)?)\s*in\b", label, re.I)
    if m:
        out["in"] = float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", label, re.I)
    if m:
        out["mm"] = float(m.group(1))
    return out


def downlight_geometry(facts: ProductFacts) -> Dict[str, Any]:
    """The recessed-downlight housing facts derived from the measured meshes
    (feet + inches), plus the pset-stated aperture / height.  Used by
    :mod:`rvt.ifc.famfrom_ifc` to size OUR housing forms.  Every number is
    MEASURED from our IFC's tessellation (bounding boxes) or STATED in its
    pset -- none is invented; a missing part yields ``None``.
    """
    def _opt(name: str) -> Optional[MeshPart]:
        try:
            return facts.part(name)
        except KeyError:
            return None

    can = _opt("housing_can")
    trim = _opt("trim_reflector")
    lens = _opt("lens")
    frame = _opt("plaster_frame")
    jbox = _opt("junction_box")
    drv = _opt("driver_box")
    bar_f = _opt("hanger_bar_front")
    bar_b = _opt("hanger_bar_back")

    def dia_ft(p: Optional[MeshPart]) -> Optional[float]:
        if p is None:
            return None
        return _r(max(p.dims_ft["x"], p.dims_ft["y"]))

    ap_label = str(facts.pset_value("Aperture") or "")
    ap = _parse_aperture_label(ap_label)
    height_stated_m = facts.pset_value("OverallHeightMeters")
    geo: Dict[str, Any] = {
        # can (housing_can mesh)
        "can_diameter_ft": dia_ft(can),
        "can_diameter_in": (_r(dia_ft(can) * 12.0) if can else None),
        "can_height_ft": (_r(can.dims_ft["z"]) if can else None),
        "can_base_z_ft": (_r(can.bbox_ft[0][2]) if can else None),
        "can_top_z_ft": (_r(can.bbox_ft[1][2]) if can else None),
        "can_center_ft": (can.center_ft() if can else None),
        # trim ring (trim_reflector mesh) / lens
        "trim_diameter_ft": dia_ft(trim),
        "trim_diameter_in": (_r(dia_ft(trim) * 12.0) if trim else None),
        "trim_top_z_ft": (_r(trim.bbox_ft[1][2]) if trim else None),
        "lens_diameter_ft": dia_ft(lens),
        "lens_z_ft": (_r((lens.bbox_ft[0][2] + lens.bbox_ft[1][2]) / 2.0) if lens else None),
        # plaster frame (mounting frame plate)
        "frame_length_ft": (_r(frame.dims_ft["x"]) if frame else None),
        "frame_width_ft": (_r(frame.dims_ft["y"]) if frame else None),
        "frame_z_ft": (_r(frame.bbox_ft[0][2]) if frame else None),
        "frame_thickness_ft": (_r(frame.dims_ft["z"]) if frame else None),
        "frame_center_ft": (frame.center_ft() if frame else None),
        # junction box + driver box
        "jbox_dims_ft": ([_r(jbox.dims_ft[a]) for a in ("x", "y", "z")] if jbox else None),
        "jbox_center_ft": (jbox.center_ft() if jbox else None),
        "jbox_base_z_ft": (_r(jbox.bbox_ft[0][2]) if jbox else None),
        "driver_dims_ft": ([_r(drv.dims_ft[a]) for a in ("x", "y", "z")] if drv else None),
        "driver_center_ft": (drv.center_ft() if drv else None),
        "driver_base_z_ft": (_r(drv.bbox_ft[0][2]) if drv else None),
        # bar hangers
        "hanger_span_ft": (_r(max(bar_f.dims_ft["x"], bar_b.dims_ft["x"]))
                           if (bar_f and bar_b) else None),
        "hanger_bar_section_ft": ([_r(bar_f.dims_ft["y"]), _r(bar_f.dims_ft["z"])]
                                  if bar_f else None),
        "hanger_offset_y_ft": (_r(abs(bar_f.center_ft()[1])) if bar_f else None),
        "hanger_base_z_ft": (_r(bar_f.bbox_ft[0][2]) if bar_f else None),
        # aperture / height from the pset (STATED, not measured)
        "aperture_label": ap_label,
        "aperture_stated_in": ap["in"],
        "aperture_stated_mm": ap["mm"],
        "overall_height_stated_m": (float(height_stated_m)
                                    if isinstance(height_stated_m, (int, float)) else None),
        # measured overall envelope
        "overall_dims_ft": dict(facts.overall_dims_ft),
        "overall_dims_in": dict(facts.overall_dims_in),
        "measured_height_ft": _r(facts.overall_dims_ft["z"]),
    }
    if geo["aperture_stated_in"] is not None:
        geo["aperture_stated_ft"] = _r(geo["aperture_stated_in"] / 12.0)
    else:
        geo["aperture_stated_ft"] = None
    if geo["overall_height_stated_m"] is not None:
        geo["overall_height_stated_ft"] = _r(geo["overall_height_stated_m"] * FT_PER_M)
    else:
        geo["overall_height_stated_ft"] = None
    return geo


# ---------------------------------------------------------------------------
# the facts RECORD (rvt.famgen.catalog facts-store schema)
# ---------------------------------------------------------------------------

def _relpath(p: str) -> str:
    try:
        r = os.path.relpath(p, _ROOT)
    except ValueError:                                         # pragma: no cover
        return p
    return p if r.startswith("..") else r.replace(os.sep, "/")


def to_facts_record(facts: ProductFacts, *, vendor: str = "own-ifc",
                    line: str = "chicago-plenum-downlight",
                    model: Optional[str] = None,
                    revit_category: str = "OST_LightingFixtures",
                    category: str = "luminaire") -> Dict[str, Any]:
    """The product facts as a ``rvt.famgen.catalog`` facts-store RECORD
    (``docs/writer/facts-store.md`` §2), self-validating (see
    :func:`validate_record`).

    ``vendor`` is ``own-ifc`` because this line's source is OUR OWN IFC
    document (Claude-Design / three-d-stage authoring), not a manufacturer
    catalog: the collection posture is "we read our own file".  Every value
    taken FROM the file is provenance ``fact`` (source ``S1`` = the IFC
    itself, ``VERIFIED``, sha256 pinned); values the file does not state
    (input voltage, wattage, delivered lumens, colour temperature -- the
    fixture carries no electrical / photometric pset) are ``null`` with
    provenance ``assumed`` (the catalog's NOT-SOURCED convention: a null is
    never a fact) so the constructor surfaces them as unset, editable
    parameters instead of inventing them.
    """
    geo = downlight_geometry(facts)
    prod = facts.product
    tag = str(prod.get("tag") or "")
    model = model or (tag if tag else _slug_model(prod.get("name") or line))
    src_rel = _relpath(facts.source_path)
    pset_names = sorted(facts.psets)
    props = {}
    for pn in pset_names:
        for k, v in facts.psets[pn].items():
            props[k] = v

    def _pv(name: str) -> Any:
        e = props.get(name)
        return None if e is None else e.get("value")

    # -- line-level facts (geometry policy + what the file states) --------------
    line_facts: Dict[str, Any] = {
        "ifc_source": {
            "value": {"path": src_rel, "sha256": facts.source_sha256,
                      "bytes": facts.source_bytes, "schema": facts.schema,
                      "application": facts.application,
                      "product_class": prod.get("ifc_class"),
                      "global_id": prod.get("global_id")},
            "provenance": "fact", "source": "S1",
            "note": "OUR OWN IFC document (Claude-Design authoring), read this session by "
                    "rvt.ifc.product_facts -- the source of every 'fact' in this record."},
        "geometry_representation": {
            "value": {"type": "Tessellation (IfcTriangulatedFaceSet meshes)",
                      "meshes": facts.counts["meshes"], "points": facts.counts["points"],
                      "faces": facts.counts["faces"],
                      "surface_styles": facts.counts["surface_styles"]},
            "provenance": "fact", "source": "S1",
            "note": "measured from the body representation; per-mesh bboxes below are in the "
                    "product's own local frame (world placement is identity)."},
        "overall_bbox_ft": {"value": {"min": facts.overall_bbox_ft[0],
                                      "max": facts.overall_bbox_ft[1],
                                      "dims": facts.overall_dims_ft},
                            "unit": "ft", "provenance": "fact", "source": "S1",
                            "note": "the whole product envelope incl. the telescoping bar "
                                    "hangers (which set the x extent) and nail flags"},
        "part_bboxes_ft": {"value": {p.name: {"min": p.bbox_ft[0], "max": p.bbox_ft[1],
                                              "dims": p.dims_ft, "role": p.role,
                                              "style": p.style, "faces": p.n_faces}
                                     for p in facts.parts},
                           "unit": "ft", "provenance": "fact", "source": "S1",
                           "note": "one entry per IfcStyledItem-named mesh; role = our "
                                   "functional classification (rvt.ifc.product_facts.classify_part)"},
        "surface_colours": {"value": {n: {"rgb": s.get("rgb"), "parts": s.get("parts")}
                                      for n, s in facts.surface_styles.items()},
                            "provenance": "fact", "source": "S1",
                            "note": "IfcSurfaceStyleRendering.SurfaceColour (sRGB 0..1)"},
        "housing_geometry_ft": {"value": geo, "unit": "ft (in / mm noted per key)",
                                "provenance": "fact", "source": "S1",
                                "note": "the recessed-can housing facts DERIVED from the "
                                        "measured meshes (can / trim / frame / boxes / "
                                        "hangers) + the pset-stated aperture and overall "
                                        "height -- the numbers OUR family forms are sized "
                                        "from; measurement, not fabrication."},
        "aperture_nominal_in": {"value": geo.get("aperture_stated_in"), "unit": "in",
                                "provenance": ("fact" if geo.get("aperture_stated_in")
                                               is not None else "assumed"),
                                "source": "S1",
                                "note": f"parsed from the pset 'Aperture' label "
                                        f"{geo.get('aperture_label')!r} (states both "
                                        f"{geo.get('aperture_stated_in')} in and "
                                        f"{geo.get('aperture_stated_mm')} mm)"},
        "overall_height_stated_ft": {"value": geo.get("overall_height_stated_ft"), "unit": "ft",
                                     "provenance": ("fact" if geo.get("overall_height_stated_ft")
                                                    is not None else "assumed"),
                                     "source": "S1",
                                     "note": f"pset 'OverallHeightMeters' = "
                                             f"{geo.get('overall_height_stated_m')} m (a STATED "
                                             f"value; the tessellation measures "
                                             f"{facts.overall_dims_m['z']} m -- both recorded)"},
        "photometry_reference": {"value": None, "provenance": "assumed", "source": "S1",
                                 "note": "NOT SOURCED -- the IFC carries no photometric web "
                                         "(IES) reference and no light-source data; the family "
                                         "exposes an empty 'Photometric Web File' REFERENCE "
                                         "parameter (a URL/path the user supplies; never an "
                                         "embedded .ies payload, per the facts-store rule)."},
        "electrical_ratings": {"value": None, "provenance": "assumed", "source": "S1",
                               "note": "NOT SOURCED -- no wattage / voltage / lumens / CCT "
                                       "pset in the IFC (the lamp is only described as "
                                       "'Integrated LED module'); the family carries these as "
                                       "unset (0) parameters and takes voltage as a job "
                                       "parameter for the connector."},
    }

    # -- the variant (the one product) --------------------------------------------
    ratings: Dict[str, Any] = {
        "aperture_in": geo.get("aperture_stated_in"),           # stated (label)
        "housing_can_diameter_in": geo.get("can_diameter_in"),  # measured
        "overall_height_in": (_r(geo["overall_height_stated_ft"] * 12.0)
                              if geo.get("overall_height_stated_ft") is not None else None),
        "measured_height_in": _r(facts.overall_dims_in["z"]),
        "lamp": _pv("Lamp"),
        "wattage_w": None,                                       # NOT SOURCED
        "lumens_lm": None,                                       # NOT SOURCED
        "cct_k": None,                                           # NOT SOURCED
        "voltage_v": None,                                       # NOT SOURCED
    }
    options: Dict[str, Any] = {
        "ccea_rating": _pv("Rating"),
        "housing": _pv("Housing"),
        "trim": _pv("Trim"),
        "mounting": _pv("Mounting"),
        "aperture_label": (str(_pv("Aperture")) if _pv("Aperture") is not None else None),
        "predefined_type": prod.get("predefined_type") or None,
        "photometric_web_file": None,                            # REFERENCE, unset
    }
    dims_in = {                                                  # the product envelope
        "w": _r(facts.overall_dims_in["x"], 3),                  # incl. bar hangers
        "d": _r(facts.overall_dims_in["y"], 3),
        "h": _r(facts.overall_dims_in["z"], 3),
    }
    fp: Dict[str, str] = {}
    for k in ratings:
        fp[f"ratings.{k}"] = "fact" if ratings[k] is not None else "assumed"
    for k in options:
        fp[f"options.{k}"] = "fact" if options[k] is not None else "assumed"
    for k in dims_in:
        fp[f"dims_in.{k}"] = "fact" if dims_in[k] is not None else "assumed"
    variant = {
        "model": model,
        "aliases": sorted({a for a in (tag, str(prod.get("name") or ""),
                                       str(prod.get("global_id") or "")) if a and a != model}),
        "role": (str(prod.get("description") or "")
                 or "recessed downlight measured from our IFC"),
        "ratings": ratings,
        "dims_in": dims_in,
        "options": options,
        "geometry_ft": {"overall_bbox": {"min": facts.overall_bbox_ft[0],
                                         "max": facts.overall_bbox_ft[1],
                                         "dims": facts.overall_dims_ft},
                        "housing": geo,
                        "parts": {p.name: {"role": p.role, "min": p.bbox_ft[0],
                                           "max": p.bbox_ft[1], "dims": p.dims_ft}
                                  for p in facts.parts}},
        "surface_colours": {n: s.get("rgb") for n, s in facts.surface_styles.items()},
        "psets": {pn: {k: {"value": v.get("value"), "ifc_type": v.get("ifc_type")}
                       for k, v in facts.psets[pn].items()} for pn in pset_names},
        "source": {"url": src_rel, "doc": (f"{facts.project_name or 'IFC product'} -- "
                                            f"{prod.get('ifc_class')} '{prod.get('name')}' "
                                            f"(GlobalId {prod.get('global_id')})"),
                   "accessed": facts.extracted_at or time.strftime("%Y-%m-%d"),
                   "sha256": facts.source_sha256},
        "field_provenance": fp,
        "notes": ("Every non-null value is a FACT read from OUR OWN IFC document this session "
                  "(measured bounding boxes / stated psets / surface colours). Nulls "
                  "(wattage, lumens, cct, voltage, photometric web) are NOT SOURCED -- the "
                  "IFC states none of them -- and are never invented; the generated family "
                  "carries them as unset parameters. dims_in is the whole product envelope "
                  "(w spans the telescoping bar hangers)."),
    }
    record: Dict[str, Any] = {
        "schema_version": 1,
        "vendor": vendor,
        "line": line,
        "product_line": (f"{facts.project_name} -- our own IFC4 recessed 6 in downlight "
                         f"(Chicago-plenum / CCEA-rated housing), extracted product facts"),
        "category": category,
        "revit_category": revit_category,
        "purpose": ("FACTS for OUR generated recessed-downlight family (rvt.ifc.famfrom_ifc): "
                    "the housing envelope, sub-part boxes and colours come from our own IFC's "
                    "tessellation; the CCEA rating / aperture / lamp / mounting from its pset. "
                    "The geometry and parameters of the family are OUR expression; the IFC "
                    "supplies the numbers."),
        "license_note": ("The source is OUR OWN authored IFC (no third-party content). Product "
                         "facts are not copyrightable in any case; no manufacturer file, image, "
                         "photometry or prose is stored. Photometry is a user-supplied "
                         "reference parameter, never bundled."),
        "collection_posture": {
            "summary": ("Direct read of our own IFC document by rvt.ifc.product_facts "
                        "(ifcopenshell); no third-party site fetched, no scraping, no external "
                        "collection question -- provenance is ours end to end."),
            "primary_reachable": True,
            "method": "local file read (our own IFC); sha256 pinned in sources.S1",
        },
        "sources": {
            "S1": {"url": src_rel,
                   "canonical_url": src_rel,
                   "doc": (f"{facts.project_name} -- OUR IFC4 file "
                           f"({facts.application or 'Claude-Design IFC writer'}); "
                           f"{prod.get('ifc_class')} '{prod.get('name')}', tag "
                           f"'{prod.get('tag')}', GlobalId {prod.get('global_id')}"),
                   "publisher": "us (Claude Design / three-d-stage IFC writer)",
                   "doc_date": None,
                   "accessed": facts.extracted_at or time.strftime("%Y-%m-%d"),
                   "verification": "VERIFIED",
                   "sha256": facts.source_sha256,
                   "note": "OUR OWN authored document; read directly this session -- "
                           "the source of every 'fact' below."},
        },
        "line_facts": line_facts,
        "variants": [variant],
    }
    return record


def _slug_model(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-").upper()[:40] or "PRODUCT"


def validate_record(record: Dict[str, Any]) -> List[str]:
    """Validate a facts record with the facts-store's own validator
    (``rvt.famgen.catalog.validate_line``) plus the store's provenance
    hygiene: a null value is never flagged ``fact`` and a ``VERIFIED``
    source carries an accessed date.  Returns a list of problems (empty =
    valid)."""
    try:
        from ..famgen import catalog as C
    except Exception as e:                                      # pragma: no cover
        return [f"catalog validator unavailable: {e}"]
    probs = list(C.validate_line(record))
    for v in record.get("variants") or []:
        fp = v.get("field_provenance") or {}
        for path in C.leaf_paths(v):
            val = C._get_path(v, path)
            if val is None and fp.get(path) == "fact":
                probs.append(f"{v.get('model')}: null {path} flagged 'fact' (nulls are never facts)")
    for sid, s in (record.get("sources") or {}).items():
        if s.get("verification") == "VERIFIED" and not s.get("accessed"):
            probs.append(f"source {sid}: VERIFIED needs an accessed date")
    return probs


def write_facts_record(facts: ProductFacts, path: str = DEFAULT_FACTS_JSON, *,
                       full_dump_path: Optional[str] = None,
                       **record_kw: Any) -> Dict[str, Any]:
    """Write the catalog-schema facts record to ``path`` (and, optionally,
    the full raw :class:`ProductFacts` dump beside it).  Refuses to write a
    record that fails :func:`validate_record`.  Returns
    ``{path, problems, record, full_dump}``."""
    rec = to_facts_record(facts, **record_kw)
    probs = validate_record(rec)
    if probs:
        raise ProductFactsError("facts record fails validation:\n  " + "\n  ".join(probs))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out = {"path": path, "problems": probs, "record": rec, "full_dump": None}
    if full_dump_path:
        with open(full_dump_path, "w", encoding="utf-8") as fh:
            json.dump(facts.to_json(), fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        out["full_dump"] = full_dump_path
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="rvt.ifc.product_facts",
                                 description="extract a product-facts record from an IFC product")
    ap.add_argument("ifc", nargs="?", default=DEFAULT_IFC, help="IFC file (default: the flagship)")
    ap.add_argument("-o", "--out", default=DEFAULT_FACTS_JSON,
                    help="facts record (catalog schema) output path")
    ap.add_argument("--full", default=None, help="also write the full raw facts dump here")
    ap.add_argument("--class", dest="cls", default=None, help="IFC product class")
    ap.add_argument("--guid", default=None, help="IFC product GlobalId")
    ap.add_argument("--json", action="store_true", help="print the record JSON to stdout")
    ap.add_argument("--no-write", action="store_true", help="extract + validate only")
    a = ap.parse_args(argv)
    facts = extract_product_facts(a.ifc, product_class=a.cls, product_guid=a.guid)
    rec = to_facts_record(facts)
    probs = validate_record(rec)
    print(f"IFC        : {facts.source_path}")
    print(f"schema     : {facts.schema}   application: {facts.application}")
    print(f"product    : {facts.product['ifc_class']} '{facts.product['name']}' "
          f"(tag {facts.product['tag']!r}, GlobalId {facts.product['global_id']})")
    print(f"psets      : {facts.counts['psets']} pset(s), {facts.counts['properties']} properties")
    for pn, props in facts.psets.items():
        for k, v in props.items():
            print(f"             {pn}.{k} = {v['value']!r} [{v['ifc_type']}]")
    d = facts.overall_dims_ft
    print(f"geometry   : {facts.counts['meshes']} meshes / {facts.counts['faces']} faces / "
          f"{facts.counts['surface_styles']} styles; overall {d['x']:.4f} x {d['y']:.4f} x "
          f"{d['z']:.4f} ft")
    print(f"validation : {'OK (schema-valid facts record)' if not probs else 'PROBLEMS'}")
    for p in probs:
        print("   -", p)
    if not a.no_write:
        write_facts_record(facts, a.out, full_dump_path=a.full)
        print(f"wrote      : {a.out}" + (f"  (+ {a.full})" if a.full else ""))
    if a.json:
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 1 if probs else 0


if __name__ == "__main__":
    raise SystemExit(main())

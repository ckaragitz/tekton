"""bridge_lib.py -- shared analysis engine for the tekton-ifc skill.

Everything the CLIs (validate_ifc.py, harden_ifc.py, report.py) need to
inspect an IFC file for *Revit fidelity*: not just "is it valid IFC" but
"what will Revit make of it".  Pure ifcopenshell + numpy; no geometry
kernel (OpenCascade) is required, which keeps sandbox runs fast and lets us
analyse the exact vertices the author wrote instead of a re-tessellation.

Public entry point: ``analyze(path) -> dict`` (the full JSON report).
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import ifcopenshell
import ifcopenshell.util.element as _ue
import ifcopenshell.util.placement as _up
import ifcopenshell.validate as _validate

ENGINE_VERSION = "0.1.0"

# --------------------------------------------------------------------------- #
# constants / heuristics
# --------------------------------------------------------------------------- #

# names (element / styled item / material) that betray annotation graphics
# exported as building solids ("phantom solids")
PHANTOM_NAME_RX = re.compile(
    r"(clearance|door[_ ]?swing|swing[_ ]?arc|keep[- ]?out|no[- ]?go|"
    r"zone|helper|annotation|leader|dimension|centerline|"
    r"working[_ ]?space)", re.I)

TESSELLATED_ITEM = ("IfcTriangulatedFaceSet", "IfcPolygonalFaceSet",
                    "IfcTriangulatedIrregularNetwork", "IfcFacetedBrep",
                    "IfcFaceBasedSurfaceModel", "IfcShellBasedSurfaceModel")
SWEPT_ITEM = ("IfcExtrudedAreaSolid", "IfcExtrudedAreaSolidTapered",
              "IfcRevolvedAreaSolid", "IfcRevolvedAreaSolidTapered",
              "IfcSurfaceCurveSweptAreaSolid", "IfcFixedReferenceSweptAreaSolid",
              "IfcSweptDiskSolid")
BREP_ITEM = ("IfcAdvancedBrep", "IfcAdvancedBrepWithVoids",
             "IfcFacetedBrepWithVoids", "IfcManifoldSolidBrep")
CSG_ITEM = ("IfcBooleanResult", "IfcBooleanClippingResult", "IfcCsgSolid")

# IFC class -> the Revit category the (link) importer maps it to.
REVIT_CATEGORY = {
    "IfcElectricDistributionBoard": "Electrical Equipment",
    "IfcTransformer": "Electrical Equipment",
    "IfcElectricGenerator": "Electrical Equipment",
    "IfcSwitchingDevice": "Electrical Equipment",
    "IfcProtectiveDevice": "Electrical Equipment",
    "IfcLightFixture": "Lighting Fixtures",
    "IfcOutlet": "Electrical Fixtures",
    "IfcCableCarrierSegment": "Cable Trays",
    "IfcCableSegment": "Conduits",
    "IfcJunctionBox": "Electrical Fixtures",
    "IfcDiscreteAccessory": "Specialty Equipment / Generic Models",
    "IfcMechanicalFastener": "Generic Models",
    "IfcBuildingElementProxy": "Generic Models",
    "IfcWall": "Walls", "IfcWallStandardCase": "Walls", "IfcCurtainWall": "Walls",
    "IfcSlab": "Floors", "IfcRoof": "Roofs", "IfcCovering": "Ceilings/Floors",
    "IfcColumn": "Structural Columns", "IfcBeam": "Structural Framing",
    "IfcDoor": "Doors", "IfcWindow": "Windows", "IfcStair": "Stairs",
    "IfcRailing": "Railings", "IfcFurniture": "Furniture",
    "IfcSpace": "Rooms/Spaces (imported as space volume)",
    "IfcOpeningElement": "Openings (consumed)",
    "IfcFlowTerminal": "Mechanical/Plumbing Fixtures",
    "IfcDuctSegment": "Ducts", "IfcPipeSegment": "Pipes",
}

SPATIAL = ("IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace",
           "IfcFacility", "IfcFacilityPart", "IfcSpatialZone")


def _f(x, nd=4):
    return round(float(x), nd)


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #

def compose_placement(product) -> np.ndarray:
    """World 4x4 of a product's ObjectPlacement (identity if none)."""
    if getattr(product, "ObjectPlacement", None) is None:
        return np.eye(4)
    try:
        return np.array(_up.get_local_placement(product.ObjectPlacement), float)
    except Exception:
        return np.eye(4)


def is_identity(m: np.ndarray, tol=1e-6) -> bool:
    return bool(np.allclose(m, np.eye(4), atol=tol))


def faceset_points_tris(item):
    """(points Nx3, tris Mx3 zero-based) for a tessellated item, else (None,None)."""
    if item.is_a("IfcTriangulatedFaceSet") or item.is_a("IfcTriangulatedIrregularNetwork"):
        pts = np.array(item.Coordinates.CoordList, float)
        idx = np.array(item.CoordIndex, int)
        if item.PnIndex:  # optional indirection
            pn = np.array(item.PnIndex, int)
            idx = pn[idx - 1]
        return pts, idx - 1
    if item.is_a("IfcPolygonalFaceSet"):
        pts = np.array(item.Coordinates.CoordList, float)
        tris = []
        for face in item.Faces:
            ci = list(face.CoordIndex)
            for k in range(1, len(ci) - 1):        # fan-triangulate for auditing
                tris.append((ci[0], ci[k], ci[k + 1]))
        return pts, np.array(tris, int) - 1
    return None, None


def _rect_from_ring(bot: np.ndarray, tol=1e-6):
    """4 coplanar points -> (centre, xdir, xdim, ydim) if a rectangle else None."""
    c = bot.mean(0)
    ang = np.arctan2(bot[:, 1] - c[1], bot[:, 0] - c[0])
    ring = bot[np.argsort(ang)]
    e = [ring[(i + 1) % 4] - ring[i] for i in range(4)]
    if not (abs(np.linalg.norm(e[0]) - np.linalg.norm(e[2])) < 1e-5
            and abs(np.linalg.norm(e[1]) - np.linalg.norm(e[3])) < 1e-5):
        return None
    if abs(np.dot(e[0], e[1])) > 1e-6 * max(1.0, np.linalg.norm(e[0]) * np.linalg.norm(e[1])) + 1e-8:
        return None
    xd, yd = np.linalg.norm(e[0]), np.linalg.norm(e[1])
    if xd < tol or yd < tol:
        return None
    xdir = e[0] / xd
    return c, xdir, xd, yd


def box_from_points(pts: np.ndarray, tol=1e-5):
    """If `pts` (any count) are exactly the 8 corners of a rectangular prism
    that is upright (rotation allowed about Z only), return
    {origin_base_centre[3], xdir[3], xdim, ydim, height}; else None."""
    if pts is None or len(pts) == 0:
        return None
    u = np.unique(np.round(pts, 5), axis=0)
    if len(u) != 8:
        return None
    zs = np.unique(np.round(u[:, 2], 5))
    if len(zs) != 2:
        return None
    z0, z1 = zs
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
    # top must be bottom translated by +h in z
    tb = np.round(np.sort(np.round(top[:, :2], 5), axis=0), 5)
    bb = np.round(np.sort(np.round(bot[:, :2], 5), axis=0), 5)
    if not np.allclose(tb, bb, atol=1e-4):
        return None
    return {
        "origin": [float(c[0]), float(c[1]), float(z0)],   # base-centre (insertion pt)
        "xdir": [float(xdir[0]), float(xdir[1]), 0.0],
        "xdim": float(xd), "ydim": float(yd), "height": float(h),
    }


def decompose_boxes(pts, tris):
    """Split a triangle soup into connected components and test each as a box.
    Returns (boxes, n_components) where boxes is the list of exact boxes; the
    item is 'all boxes' only if len(boxes) == n_components."""
    if pts is None or tris is None or len(tris) == 0:
        return [], 0
    # union-find on vertices via triangles, on *rounded coordinates* so that
    # duplicated per-face vertices (the three.js pattern) still connect.
    key = [tuple(np.round(p, 5)) for p in pts]
    parent = {k: k for k in key}

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
        union(key[a], key[b]); union(key[b], key[c])
    comps = defaultdict(list)          # root -> triangle list
    for t in tris:
        comps[find(key[t[0]])].append(t)
    boxes = []
    for root, ts in comps.items():
        vidx = sorted({int(i) for t in ts for i in t})
        comp_pts = pts[vidx]
        if len(ts) != 12:              # a box is 6 quads = 12 triangles
            continue
        b = box_from_points(comp_pts)
        if b:
            b["triangles"] = 12
            boxes.append(b)
    return boxes, len(comps)


def classify_item(item) -> str:
    if item.is_a("IfcMappedItem"):
        src = item.MappingSource.MappedRepresentation
        kinds = sorted({classify_item(i) for i in src.Items}) or ["empty"]
        return "mapped(" + "+".join(kinds) + ")"
    for k in TESSELLATED_ITEM:
        if item.is_a(k):
            return "tessellated"
    for k in SWEPT_ITEM:
        if item.is_a(k):
            return "swept"
    for k in BREP_ITEM:
        if item.is_a(k):
            return "brep"
    for k in CSG_ITEM:
        if item.is_a(k):
            return "csg"
    if item.is_a("IfcBoundingBox"):
        return "bbox"
    if item.is_a("IfcGeometricSet") or item.is_a("IfcGeometricCurveSet"):
        return "curveset"
    return item.is_a().lower()


def styled_name_and_style(f, item):
    """(styled item name, transparency, style names) for a representation item."""
    name, transp, styles = None, 0.0, []
    inv = f.get_inverse(item)
    for si in inv:
        if si.is_a("IfcStyledItem"):
            name = si.Name or name
            for pa in si.Styles or []:
                targets = pa.Styles if pa.is_a("IfcPresentationStyleAssignment") else [pa]
                for st in targets:
                    if st is None:
                        continue
                    styles.append(getattr(st, "Name", None) or st.is_a())
                    if st.is_a("IfcSurfaceStyle"):
                        for rend in st.Styles:
                            if rend.is_a("IfcSurfaceStyleRendering") and rend.Transparency:
                                transp = max(transp, float(rend.Transparency))
    return name, transp, styles


# --------------------------------------------------------------------------- #
# audits
# --------------------------------------------------------------------------- #

def schema_audit(f) -> dict:
    logger = _validate.json_logger()
    try:
        _validate.validate(f, logger, express_rules=False)
    except Exception as e:  # pragma: no cover
        return {"ran": False, "error": str(e), "errors": [], "warnings": [], "n_errors": -1}
    errs, warns = [], []
    for s in logger.statements:
        lvl = str(s.get("level", "")).upper()
        msg = s.get("message", "")
        inst = s.get("instance", None)
        rec = {"level": lvl, "message": msg, "instance": str(inst) if inst is not None else None}
        (errs if lvl == "ERROR" else warns).append(rec)
    return {"ran": True, "schema": f.schema, "n_statements": len(logger.statements),
            "n_errors": len(errs), "n_warnings": len(warns),
            "errors": errs[:200], "warnings": warns[:200]}


def entity_histogram(f) -> dict:
    c = Counter(e.is_a() for e in f)
    return dict(c.most_common())


def element_products(f):
    """All non-spatial products with a physical presence (IfcElement subtypes)."""
    return [p for p in f.by_type("IfcProduct")
            if p.is_a("IfcElement") and not p.is_a("IfcOpeningElement")]


def product_geometry(f, prod) -> dict:
    """Per-product geometry audit."""
    out = {"has_body": False, "kinds": [], "items": [], "tri_count": 0,
           "faceset_count": 0, "swept_count": 0, "mapped": False,
           "all_boxes": False, "boxes": [], "predicted_revit": None,
           "min_dimension": None, "footprint_area": None}
    reps = prod.Representation.Representations if getattr(prod, "Representation", None) else []
    all_boxes_flag, any_tess = True, False
    box_list = []
    mins, extents = [], []
    for rep in reps:
        ident = rep.RepresentationIdentifier or ""
        for item in rep.Items:
            kind = classify_item(item)
            rec = {"rep_identifier": ident, "rep_type": rep.RepresentationType,
                   "item": item.is_a(), "kind": kind, "id": item.id()}
            name, transp, styles = styled_name_and_style(f, item)
            rec["style_name"] = name
            rec["transparency"] = _f(transp, 3)
            if kind.startswith("mapped"):
                out["mapped"] = True
                try:
                    rec["map_id"] = item.MappingSource.id()
                except Exception:
                    pass
            if kind == "tessellated":
                any_tess = True
                out["faceset_count"] += 1
                pts, tris = faceset_points_tris(item)
                ntri = 0 if tris is None else len(tris)
                out["tri_count"] += ntri
                rec["triangles"] = ntri
                if pts is not None and len(pts):
                    ext = pts.max(0) - pts.min(0)
                    rec["extent"] = [_f(x) for x in ext]
                    mins.append(float(ext.min()))
                    extents.append(sorted(ext.tolist()))
                boxes, ncomp = decompose_boxes(pts, tris)
                rec["boxes_found"] = len(boxes)
                rec["components"] = ncomp
                rec["is_box"] = (len(boxes) == ncomp and ncomp > 0)
                if not rec["is_box"]:
                    all_boxes_flag = False
                box_list.extend(boxes)
            elif kind == "swept":
                out["swept_count"] += 1
                if item.is_a("IfcExtrudedAreaSolid"):
                    rec["depth"] = _f(item.Depth)
                    prof = item.SweptArea
                    rec["profile"] = prof.is_a() if prof else None
                    if prof is not None:
                        if prof.is_a("IfcRectangleProfileDef"):
                            rec["profile_dims"] = (_f(prof.XDim), _f(prof.YDim))
                        elif prof.is_a("IfcCircleProfileDef"):
                            rec["profile_dims"] = (_f(prof.Radius),)
                        elif prof.is_a("IfcArbitraryClosedProfileDef"):
                            oc = prof.OuterCurve
                            if oc.is_a("IfcPolyline"):
                                rec["profile_dims"] = tuple(
                                    _f(c) for p in oc.Points for c in p.Coordinates)
                            elif oc.is_a("IfcIndexedPolyCurve"):
                                rec["profile_dims"] = tuple(
                                    _f(c) for p in oc.Points.CoordList for c in p)
            out["items"].append(rec)
            out["kinds"].append(kind)
    out["has_body"] = bool(out["items"])
    if any_tess:
        out["all_boxes"] = bool(all_boxes_flag and box_list)
        out["boxes"] = box_list
    if mins:
        out["min_dimension"] = _f(min(mins))
    if extents:
        # largest planar face area proxy = product of two largest dims of the largest item
        big = max(extents, key=lambda e: e[1] * e[2])
        out["footprint_area"] = _f(big[1] * big[2])
    kinds = set(out["kinds"])
    if not out["has_body"]:
        pred = "no geometry"
    elif "tessellated" in kinds:
        pred = ("DirectShape mesh blob (categorized/schedulable, faceted, "
                "not parametrically editable, no meaningful insertion point)")
    elif any(k.startswith("mapped") for k in kinds) and out["swept_count"] == 0:
        inner = ",".join(sorted(kinds))
        pred = ("DirectShape from mapped/instanced geometry (" + inner +
                "): shared type geometry, clean solid, movable")
    elif "swept" in kinds or any("swept" in k for k in kinds):
        pred = ("DirectShape clean solid (extrusion; dimensionally honest, movable, "
                "real insertion point) -- may nativise for simple walls/slabs via Open IFC")
    elif "brep" in kinds:
        pred = "DirectShape solid (brep) -- clean but not parametric"
    else:
        pred = "DirectShape / kernel-dependent (" + ",".join(sorted(kinds)) + ")"
    out["predicted_revit"] = pred
    return out


def product_inventory(f) -> list[dict]:
    inv = []
    for p in element_products(f):
        t = _ue.get_type(p)
        cont = _ue.get_container(p)
        m = compose_placement(p)
        rec = {
            "step_id": p.id(),
            "guid": p.GlobalId,
            "class": p.is_a(),
            "predefined_type": getattr(p, "PredefinedType", None),
            "object_type": getattr(p, "ObjectType", None),
            "name": p.Name,
            "description": p.Description,
            "tag": getattr(p, "Tag", None),
            "type_name": t.Name if t is not None else None,
            "type_id": t.id() if t is not None else None,
            "storey": cont.Name if cont is not None else None,
            "storey_class": cont.is_a() if cont is not None else None,
            "revit_category": REVIT_CATEGORY.get(p.is_a(), "Generic Models (unmapped class)"),
            "placement_identity": is_identity(m),
            "placement_origin": [_f(x) for x in m[:3, 3]],
            "psets": _ue.get_psets(p, psets_only=True),
        }
        rec["geometry"] = product_geometry(f, p)
        inv.append(rec)
    # spaces are products too (spatial audit uses them separately)
    return inv


def type_audit(f, inventory) -> dict:
    types = f.by_type("IfcTypeObject")
    by_key = defaultdict(list)
    for t in types:
        by_key[(t.is_a(), (t.Name or "").strip())].append(t)
    dup_groups = []
    dup_objects = 0
    for (cls, name), lst in by_key.items():
        if len(lst) > 1:
            occ = 0
            for t in lst:
                occ += sum(len(r.RelatedObjects) for r in getattr(t, "Types", []) or [])
            dup_groups.append({"class": cls, "name": name, "count": len(lst),
                               "type_ids": [t.id() for t in lst], "occurrences": occ})
            dup_objects += len(lst) - 1
    untyped = [r["step_id"] for r in inventory if not r["type_id"]]
    typed = len(inventory) - len(untyped)
    return {
        "type_objects": len(types),
        "rel_defines_by_type": len(f.by_type("IfcRelDefinesByType")),
        "duplicate_groups": dup_groups,
        "duplicate_type_objects": dup_objects,
        "products_typed": typed,
        "products_untyped": len(untyped),
        "untyped_product_ids": untyped,
        "typed_fraction": _f(typed / len(inventory), 3) if inventory else 1.0,
    }


def _geom_signature(rec) -> tuple:
    g = rec["geometry"]
    sig = []
    for it in g["items"]:
        ext = tuple(round(x, 3) for x in sorted(it.get("extent", [0, 0, 0])))
        sig.append((it["item"], it.get("kind"), ext, it.get("triangles", 0),
                    it.get("depth", 0), it.get("profile"), it.get("profile_dims"),
                    it.get("map_id")))
    return (rec["class"], tuple(sorted(sig)))


HOST_ELEMENTS = ("IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcRoof",
                 "IfcCovering", "IfcCurtainWall", "IfcOpeningElement")


def instancing_audit(inventory) -> dict:
    """Repeated identical geometry that is not shared via mapped items.
    Host/system-family elements (walls, slabs, roofs) are excluded: Revit
    rebuilds those from their own extrusion, so instancing buys nothing."""
    groups = defaultdict(list)
    for rec in inventory:
        if not rec["geometry"]["has_body"] or rec["class"] in HOST_ELEMENTS:
            continue
        groups[_geom_signature(rec)].append(rec)
    repeated = []
    wasted_tris = 0
    unshared = 0
    for sig, members in groups.items():
        if len(members) < 2:
            continue
        shared = all(m["geometry"]["mapped"] for m in members)
        tris = members[0]["geometry"]["tri_count"]
        repeated.append({"class": sig[0], "count": len(members),
                         "names": [m["name"] for m in members][:12],
                         "uses_mapped_items": shared,
                         "triangles_each": tris,
                         "duplicated_triangles": 0 if shared else tris * (len(members) - 1)})
        if not shared:
            unshared += len(members)
            wasted_tris += tris * (len(members) - 1)
    withbody = sum(1 for r in inventory if r["geometry"]["has_body"])
    return {"repeated_groups": repeated,
            "unshared_repeated_products": unshared,
            "unshared_fraction": _f(unshared / withbody, 3) if withbody else 0.0,
            "duplicated_triangles": wasted_tris}


def phantom_audit(f, inventory) -> dict:
    """Detect annotation graphics that were exported as building solids."""
    findings = []
    for rec in inventory:
        g = rec["geometry"]
        name_hay = " ".join(str(x) for x in (rec["name"], rec["object_type"], rec["description"], rec["tag"]) if x)
        prod_reasons = []
        if PHANTOM_NAME_RX.search(name_hay):
            prod_reasons.append("element name/description matches annotation vocabulary")
        item_hits = []
        for it in g["items"]:
            r = []
            sn = it.get("style_name") or ""
            if sn and PHANTOM_NAME_RX.search(sn):
                r.append(f"geometry item named '{sn}' (annotation vocabulary)")
            if it.get("transparency", 0) >= 0.5:
                r.append(f"transparent surface (transparency={it['transparency']})")
            ext = it.get("extent")
            if ext:
                mn = min(ext)
                area = sorted(ext)[1] * sorted(ext)[2]
                if mn < 0.003 and area > 0.5:
                    r.append(f"very thin sheet ({mn*1000:.1f} mm over {area:.2f} m2)")
            if r:
                item_hits.append({"item_id": it["id"], "style_name": sn, "reasons": r})
        reasons = prod_reasons + [x for h in item_hits for x in h["reasons"]]
        if not reasons:
            continue
        strong = any(("annotation vocabulary" in r) or ("transparent" in r) for r in reasons)
        findings.append({
            "step_id": rec["step_id"], "guid": rec["guid"], "class": rec["class"],
            "name": rec["name"], "confidence": "high" if strong else "low",
            "reasons": reasons, "items": item_hits,
            "whole_product": bool(prod_reasons) or (
                len(item_hits) == len(g["items"]) and g["items"]),
        })
    return {"count": len(findings),
            "high_confidence": sum(1 for x in findings if x["confidence"] == "high"),
            "findings": findings}


def spatial_audit(f, inventory) -> dict:
    storeys = f.by_type("IfcBuildingStorey")
    spaces = f.by_type("IfcSpace")
    orphans = [r["step_id"] for r in inventory if not r["storey"]]
    per_storey = Counter(r["storey"] or "(none)" for r in inventory)
    return {
        "project": f.by_type("IfcProject")[0].Name if f.by_type("IfcProject") else None,
        "sites": len(f.by_type("IfcSite")),
        "buildings": len(f.by_type("IfcBuilding")),
        "storeys": [{"name": s.Name, "elevation": s.Elevation} for s in storeys],
        "storey_count": len(storeys),
        "single_storey": len(storeys) <= 1,
        "spaces": [{"name": s.Name, "long_name": s.LongName,
                    "predefined": getattr(s, "PredefinedType", None)} for s in spaces],
        "space_count": len(spaces),
        "orphan_element_ids": orphans,
        "orphan_count": len(orphans),
        "containment_coverage": _f(1 - len(orphans) / len(inventory), 3) if inventory else 1.0,
        "elements_per_storey": dict(per_storey),
    }


ELECTRICAL_PROP_HINTS = {
    "voltage": "IfcElectricVoltageMeasure", "volts": "IfcElectricVoltageMeasure",
    "current": "IfcElectricCurrentMeasure", "amps": "IfcElectricCurrentMeasure",
    "amperage": "IfcElectricCurrentMeasure", "rating": None,
    "power": "IfcPowerMeasure", "watts": "IfcPowerMeasure", "kva": "IfcPowerMeasure",
}


def _prop_value_type(prop):
    if prop.is_a("IfcPropertySingleValue") and prop.NominalValue is not None:
        try:
            return prop.NominalValue.is_a()
        except Exception:
            return type(prop.NominalValue).__name__
    return prop.is_a()


def pset_audit(f, inventory) -> dict:
    """Inventory of psets/props + consistency across same-class products."""
    # class -> pset name -> list of {prop: valuetype} dicts (one per product)
    seen = defaultdict(lambda: defaultdict(list))
    inventory_out = defaultdict(lambda: defaultdict(dict))
    typing_smells = []
    for prod in element_products(f):
        for rel in getattr(prod, "IsDefinedBy", []) or []:
            if not rel.is_a("IfcRelDefinesByProperties"):
                continue
            pdef = rel.RelatingPropertyDefinition
            if not pdef.is_a("IfcPropertySet"):
                continue
            sig = {}
            props = list(pdef.HasProperties)
            # measures already correctly typed in this pset (e.g. a numeric
            # IfcElectricVoltageMeasure 'Voltage'): a companion human-readable
            # label like 'SystemVoltage' is then intentional, not a typing smell.
            typed_measures = {_prop_value_type(p) for p in props}
            LABEL_WORDS = ("label", "designation", "description", "display",
                           "text", "note", "name", "string")
            for pr in props:
                vt = _prop_value_type(pr)
                sig[pr.Name] = vt
                inventory_out[prod.is_a()][pdef.Name][pr.Name] = vt
                low = pr.Name.lower()
                if any(w in low for w in LABEL_WORDS):
                    continue  # deliberately-textual companion property
                for hint, expected in ELECTRICAL_PROP_HINTS.items():
                    if (hint in low and expected and vt in ("IfcLabel", "IfcText", "IfcIdentifier")
                            and expected not in typed_measures):
                        typing_smells.append({"class": prod.is_a(), "product": prod.Name,
                                             "pset": pdef.Name, "property": pr.Name,
                                             "value_type": vt, "suggested": expected})
                        break
            seen[prod.is_a()][pdef.Name].append(sig)
    inconsist = []
    checks = 0
    consistent = 0
    for cls, psets in seen.items():
        for psname, sigs in psets.items():
            if len(sigs) < 2:
                continue
            checks += 1
            base = sigs[0]
            same = all(s == base for s in sigs[1:])
            if same:
                consistent += 1
            else:
                allkeys = set().union(*[set(s) for s in sigs])
                diffs = {}
                for k in sorted(allkeys):
                    vals = {s.get(k, "<missing>") for s in sigs}
                    if len(vals) > 1:
                        diffs[k] = sorted(map(str, vals))
                inconsist.append({"class": cls, "pset": psname,
                                  "products": len(sigs), "differences": diffs})
    return {
        "by_class": {c: {ps: dict(props) for ps, props in psets.items()}
                     for c, psets in inventory_out.items()},
        "consistency_checks": checks,
        "consistent": consistent,
        "consistency_ratio": _f(consistent / checks, 3) if checks else 1.0,
        "inconsistent": inconsist,
        "typing_smells": typing_smells,
        "pset_names": sorted({ps for psets in inventory_out.values() for ps in psets}),
    }


def unit_audit(f, inventory) -> dict:
    ua = f.by_type("IfcUnitAssignment")
    units = {}
    if ua:
        for u in ua[0].Units:
            if u.is_a("IfcSIUnit"):
                units[str(u.UnitType)] = f"{u.Prefix or ''}{u.Name}"
            elif u.is_a("IfcConversionBasedUnit"):
                units[str(u.UnitType)] = f"conversion:{u.Name}"
            elif u.is_a("IfcDerivedUnit"):
                units[str(u.UnitType)] = "derived"
            elif u.is_a("IfcMonetaryUnit"):
                units["MONETARY"] = str(u.Currency)
    length = units.get("LENGTHUNIT")
    metric = length in ("METRE", "MILLIMETRE")
    classes = {r["class"] for r in inventory}
    electrical = any(c in classes for c in (
        "IfcElectricDistributionBoard", "IfcTransformer", "IfcLightFixture",
        "IfcCableCarrierSegment", "IfcElectricGenerator", "IfcOutlet"))
    missing_elec = []
    if electrical:
        for u in ("ELECTRICVOLTAGEUNIT", "ELECTRICCURRENTUNIT", "POWERUNIT"):
            if u not in units:
                missing_elec.append(u)
    issues = []
    if length is None:
        issues.append("no LENGTHUNIT defined")
    elif not metric:
        issues.append(f"length unit is {length}; Revit imports fine but metres/mm are least error-prone")
    if length == "MILLIMETRE":
        issues.append("length unit is millimetres -- fine, but keep model coordinates consistent")
    for u in missing_elec:
        issues.append(f"electrical elements present but {u} not declared")
    return {"units": units, "length_unit": length, "is_metric": bool(metric),
            "electrical_units_missing": missing_elec, "issues": issues}


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def score_report(rep: dict) -> dict:
    inv = rep["products"]
    n = len(inv)
    with_body = [r for r in inv if r["geometry"]["has_body"]]
    nb = len(with_body) or 1
    tess = sum(1 for r in with_body if "tessellated" in r["geometry"]["kinds"])
    tess_frac = tess / nb if with_body else 0.0
    ident = sum(1 for r in inv if r["placement_identity"])
    ident_frac = ident / n if n else 0.0
    ta, ia, ph, sp, ps, ua = (rep["types"], rep["instancing"], rep["phantoms"],
                              rep["spatial"], rep["psets"], rep["units"])
    schema_ok = rep["schema"].get("n_errors", 1) == 0

    dup_pen = 0.0
    if ta["type_objects"]:
        dup_pen = ta["duplicate_type_objects"] / max(1, ta["type_objects"])
    comp = {
        "schema": 1.0 if schema_ok else 0.0,
        "geometry_parametric": 1.0 - tess_frac,
        "placements": 1.0 - ident_frac,
        "typing": max(0.0, ta["typed_fraction"] * (1.0 - dup_pen)),
        "instancing": 1.0 - ia["unshared_fraction"],
        "phantom_free": max(0.0, 1.0 - 0.25 * ph["high_confidence"] - 0.05 * (ph["count"] - ph["high_confidence"])),
        "spatial": max(0.0, sp["containment_coverage"] * (0.85 if sp["single_storey"] and sp["space_count"] == 0 else 1.0)),
        "data": max(0.0, ps["consistency_ratio"] - (0.02 * len(ps["typing_smells"]))),
        "units": 1.0 if not ua["issues"] else max(0.0, 1.0 - 0.34 * len(ua["issues"])),
    }
    weights = {"schema": 8, "geometry_parametric": 28, "placements": 20, "typing": 14,
               "instancing": 6, "phantom_free": 8, "spatial": 8, "data": 4, "units": 4}
    total = sum(weights.values())
    score = 100.0 * sum(comp[k] * weights[k] for k in weights) / total

    if not schema_ok:
        tier = "INVALID (schema errors -- fix before anything else)"
    elif comp["geometry_parametric"] >= 0.95 and comp["placements"] >= 0.9 and score >= 82:
        tier = "Tier 1 -- clean, movable, dimensionally-honest reference geometry (DirectShape, no MEP connectors)"
    elif score >= 55:
        tier = "Tier 1 (partial) -- imports usably but some elements come in as frozen blobs / at the origin"
    else:
        tier = "Tier 0 (v1-like) -- imports as frozen DirectShape blobs with baked coordinates"

    # top fixes, ranked by weighted deficit
    fixes = []
    def add(cid, impact, text):
        fixes.append({"component": cid, "impact": round(impact, 2), "fix": text})
    if not schema_ok:
        add("schema", 100, f"Repair {rep['schema']['n_errors']} schema error(s) -- Revit's importer will drop or mangle invalid entities.")
    if tess:
        add("geometry_parametric", weights["geometry_parametric"] * tess_frac,
            f"{tess}/{nb} elements are triangle-mesh solids ({tess_frac:.0%} tessellated). "
            "Emit IfcExtrudedAreaSolid (box/profile extrusions) instead -> clean, dimensionally-editable solids "
            "instead of frozen faceted blobs. harden_ifc.py converts exact boxes automatically.")
    if ident:
        add("placements", weights["placements"] * ident_frac,
            f"{ident}/{n} elements have identity placements (coordinates baked into vertices; insertion points lost). "
            "Emit real IfcLocalPlacement positions per element so they can be moved/rotated in Revit.")
    if ta["duplicate_type_objects"]:
        add("typing", weights["typing"] * dup_pen,
            f"{ta['duplicate_type_objects']} redundant type object(s) in {len(ta['duplicate_groups'])} group(s) "
            "with identical (class, name). Share ONE type per name via a single IfcRelDefinesByType.")
    if ta["products_untyped"]:
        add("typing", weights["typing"] * (1 - ta["typed_fraction"]),
            f"{ta['products_untyped']}/{n} elements have no type object. Add a shared IfcXxxType per model number "
            "so Revit gets one type per catalogue item (type parameters, tags, schedules).")
    if ia["unshared_repeated_products"]:
        add("instancing", weights["instancing"] * ia["unshared_fraction"],
            f"{ia['unshared_repeated_products']} elements repeat identical geometry verbatim "
            f"({ia['duplicated_triangles']} duplicated triangles). Use IfcRepresentationMap + IfcMappedItem instancing.")
    if ph["count"]:
        add("phantom_free", weights["phantom_free"] * (1 - comp["phantom_free"]),
            f"{ph['count']} phantom annotation solid(s) (clearance/swing/helper graphics exported as building elements). "
            "Remove them or export as IfcSpace/psets -- Revit shows them as translucent blobs in every view.")
    if sp["single_storey"] and sp["space_count"] == 0 and n:
        add("spatial", weights["spatial"] * 0.15,
            "Single storey and no IfcSpace: add one IfcBuildingStorey per real level and IfcSpace for rooms "
            "so Revit gets Levels and space data.")
    if sp["orphan_count"]:
        add("spatial", weights["spatial"] * (1 - sp["containment_coverage"]),
            f"{sp['orphan_count']} element(s) lack spatial containment; contain them in a storey.")
    if ps["inconsistent"]:
        add("data", weights["data"] * (1 - ps["consistency_ratio"]),
            f"{len(ps['inconsistent'])} property set(s) differ in shape across same-class elements; "
            "keep pset property names/types identical so they map to one Revit shared parameter each.")
    if ps["typing_smells"]:
        add("data", weights["data"] * 0.3,
            f"{len(ps['typing_smells'])} electrical propert(ies) stored as plain text (e.g. Voltage as IfcLabel). "
            "Use IfcElectricVoltageMeasure/IfcElectricCurrentMeasure/IfcPowerMeasure so Revit binds them to unit-aware parameters.")
    for issue in ua["issues"]:
        add("units", weights["units"] * 0.34, "Units: " + issue + ".")
    fixes.sort(key=lambda x: -x["impact"])
    return {
        "score": round(score, 1),
        "tier": tier,
        "components": {k: round(v, 3) for k, v in comp.items()},
        "weights": weights,
        "stats": {"products": n, "with_body": len(with_body), "tessellated": tess,
                  "tessellated_fraction": _f(tess_frac, 3),
                  "identity_placements": ident, "identity_fraction": _f(ident_frac, 3)},
        "top_fixes": fixes[:5],
        "all_fixes": fixes,
    }


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #

def analyze(path: str, model=None) -> dict:
    """The full report of the IFC at ``path``; ``model`` is an already-open
    ``ifcopenshell.file`` of that same path to analyse instead of parsing it
    again (the analysis only reads it)."""
    f = ifcopenshell.open(path) if model is None else model
    inv = product_inventory(f)
    rep = {
        "engine": "tekton-ifc validate", "engine_version": ENGINE_VERSION,
        "file": os.path.abspath(path), "file_size": os.path.getsize(path),
        "schema": schema_audit(f),
        "histogram": entity_histogram(f),
        "products": inv,
        "types": type_audit(f, inv),
        "instancing": instancing_audit(inv),
        "phantoms": phantom_audit(f, inv),
        "spatial": spatial_audit(f, inv),
        "psets": pset_audit(f, inv),
        "units": unit_audit(f, inv),
    }
    rep["score"] = score_report(rep)
    return rep


def human_summary(rep: dict, width: int = 100) -> str:
    """Compact human-readable text summary of an analysis report."""
    L = []
    sc, st, ta, ia, ph, sp, ps, ua = (rep["score"], rep["score"]["stats"], rep["types"],
                                       rep["instancing"], rep["phantoms"], rep["spatial"],
                                       rep["psets"], rep["units"])
    L.append(f"tekton-ifc validate  -  {os.path.basename(rep['file'])}  ({rep['file_size']} bytes)")
    L.append("=" * min(width, 78))
    sch = rep["schema"]
    L.append(f"schema        : {sch.get('schema')}  errors={sch.get('n_errors')}  warnings={sch.get('n_warnings')}")
    L.append(f"score         : {sc['score']}/100")
    L.append(f"tier          : {sc['tier']}")
    L.append(f"elements      : {st['products']} (with geometry: {st['with_body']})")
    L.append(f"geometry      : {st['tessellated']}/{st['with_body']} tessellated "
             f"({st['tessellated_fraction']:.0%}); triangles="
             f"{sum(r['geometry']['tri_count'] for r in rep['products'])}")
    L.append(f"placements    : {st['identity_placements']}/{st['products']} identity/origin "
             f"(baked coordinates - insertion points lost)")
    L.append(f"types         : {ta['type_objects']} type objects, {ta['products_untyped']} untyped elements, "
             f"{ta['duplicate_type_objects']} duplicates in {len(ta['duplicate_groups'])} group(s)")
    L.append(f"instancing    : {ia['unshared_repeated_products']} elements repeat identical geometry unshared "
             f"({ia['duplicated_triangles']} duplicated tris)")
    L.append(f"phantoms      : {ph['count']} suspected annotation-as-solid ({ph['high_confidence']} high confidence)")
    L.append(f"spatial       : {sp['storey_count']} storey(s), {sp['space_count']} space(s), "
             f"{sp['orphan_count']} orphan(s), containment={sp['containment_coverage']:.0%}")
    L.append(f"psets         : {len(ps['pset_names'])} named sets, consistency={ps['consistency_ratio']:.0%}, "
             f"{len(ps['typing_smells'])} untyped electrical value(s)")
    L.append(f"units         : {ua['length_unit']}  " + ("(issues: " + "; ".join(ua['issues']) + ")" if ua["issues"] else "OK"))
    L.append("")
    L.append("component scores: " + ", ".join(f"{k}={v}" for k, v in sc["components"].items()))
    L.append("")
    L.append("top fixes (highest impact first):")
    for i, fx in enumerate(sc["top_fixes"], 1):
        L.append(f"  {i}. [{fx['component']}] {fx['fix']}")
    if not sc["top_fixes"]:
        L.append("  (none - looks clean)")
    L.append("")
    L.append("element inventory:")
    L.append(f"  {'class':32s} {'name':22s} {'type':18s} {'storey':10s} geometry -> predicted Revit result")
    for r in rep["products"]:
        g = r["geometry"]
        kinds = "+".join(sorted(set(g["kinds"]))) or "-"
        L.append(f"  {r['class'][:32]:32s} {str(r['name'])[:22]:22s} "
                 f"{str(r['type_name'] or '-')[:18]:18s} {str(r['storey'] or '-')[:10]:10s} "
                 f"{kinds}")
    L.append("")
    L.append("histogram (top): " + ", ".join(f"{k}={v}" for k, v in list(rep["histogram"].items())[:8]))
    return "\n".join(L)


def dump_json(rep: dict, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(rep, fh, indent=2, default=str)

#!/usr/bin/env python3
"""harden_ifc.py -- rewrite an existing IFC toward "Tier 1" Revit fidelity
WITHOUT altering the intended geometry semantics.

Usage:
    python harden_ifc.py <in.ifc> -o <out.ifc> [--report report.json]
        [--keep-clearance-as-space] [--no-remove-phantoms]
        [--no-create-types] [--no-extrusions]

Transformations (all logged; GlobalIds of products are preserved):
  * merge duplicate type objects with identical (class, Name) into one shared
    type (rewires IfcRelDefinesByType);
  * create ONE shared type per group of untyped elements that share
    (class, predefined type, geometry signature) -- e.g. six identical panels
    get one IfcElectricDistributionBoardType (disable with --no-create-types);
  * move property sets that are byte-identical across every occurrence of a
    type onto the type;
  * repair empty owner-history person/organisation/application fields;
  * detect phantom annotation solids (clearance/swing/helper graphics) and
    remove them (or --keep-clearance-as-space: axis-aligned box clearances
    become IfcSpace .INTERNAL. instead);
  * replace tessellated geometry that is PROVABLY an upright box (8 corners
    forming a rectangular prism, rotation about Z allowed) with a real
    IfcExtrudedAreaSolid, and move the element's placement to the box's
    base-centre (recovering an insertion point + orientation) -- only when
    exact, otherwise tessellation is left untouched;
  * contain any orphan elements in the first building storey.

Then reopens the output, validates the schema, and prints a before/after diff.
Exit codes: 0 ok, 1 output failed to reopen / has schema errors, 2 usage/IO.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.element as _ue
import ifcopenshell.util.placement as _up

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_lib as bl  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

class Log:
    def __init__(self):
        self.entries = []

    def add(self, action: str, **kw):
        rec = {"action": action}
        rec.update(kw)
        self.entries.append(rec)


def _guid():
    return ifcopenshell.guid.new()


def _oh(f):
    ohs = f.by_type("IfcOwnerHistory")
    return ohs[0] if ohs else None


def type_class_for(f, product_class: str):
    """The IfcXxxType entity name for a product class, if the schema has one."""
    schema = ifcopenshell.schema_by_name(f.schema)
    name = product_class + "Type"
    try:
        schema.declaration_by_name(name)
        return name
    except Exception:
        try:
            schema.declaration_by_name("IfcTypeProduct")
            return "IfcTypeProduct"
        except Exception:
            return None


def axis2placement(f, origin, xdir=(1.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0)):
    return f.createIfcAxis2Placement3D(
        f.createIfcCartesianPoint([float(x) for x in origin]),
        f.createIfcDirection([float(x) for x in zdir]),
        f.createIfcDirection([float(x) for x in xdir]),
    )


def matrix_of_frame(origin, xdir, zdir=(0.0, 0.0, 1.0)):
    x = np.array(xdir, float); x /= np.linalg.norm(x)
    z = np.array(zdir, float); z /= np.linalg.norm(z)
    y = np.cross(z, x); y /= np.linalg.norm(y)
    x = np.cross(y, z)
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x, y, z, np.array(origin, float)
    return m


def rel_placement_matrix(local_placement) -> np.ndarray:
    """4x4 of an IfcLocalPlacement's RelativePlacement only (not composed)."""
    rp = local_placement.RelativePlacement
    if rp is None:
        return np.eye(4)
    return np.array(_up.get_axis2placement(rp), float)


def styled_items_for(f, item):
    return [si for si in f.get_inverse(item) if si.is_a("IfcStyledItem")]


def remove_item_deep(f, item, log: Log):
    """Remove a representation item and its exclusively-owned children."""
    for si in styled_items_for(f, item):
        f.remove(si)
    if item.is_a("IfcTriangulatedFaceSet") or item.is_a("IfcPolygonalFaceSet"):
        coords = item.Coordinates
        f.remove(item)
        if coords is not None and not f.get_inverse(coords):
            f.remove(coords)
    else:
        try:
            _ue.remove_deep2(f, item)
        except Exception:
            f.remove(item)


# --------------------------------------------------------------------------- #
# individual transformations
# --------------------------------------------------------------------------- #

def fix_owner_history(f, log: Log):
    changed = 0
    for p in f.by_type("IfcPerson"):
        if not (p.FamilyName or p.GivenName or p.Identification):
            p.Identification = "tekton-ifc"
            p.GivenName = "tekton-ifc"
            p.FamilyName = "engine"
            changed += 1
    for o in f.by_type("IfcOrganization"):
        if not o.Name:
            o.Name = "tekton-ifc"
            changed += 1
    for a in f.by_type("IfcApplication"):
        if not a.ApplicationFullName:
            a.ApplicationFullName = "tekton-ifc hardener"
            changed += 1
        if not a.ApplicationIdentifier:
            a.ApplicationIdentifier = "tekton-ifc"
            changed += 1
        if not a.Version:
            a.Version = bl.ENGINE_VERSION
            changed += 1
    now = int(time.time())
    for oh in f.by_type("IfcOwnerHistory"):
        if oh.State is None:
            oh.State = "READWRITE"
        if oh.ChangeAction in (None, "NOCHANGE", "NOTDEFINED"):
            oh.ChangeAction = "MODIFIED"
            changed += 1
        oh.LastModifiedDate = now
        if oh.LastModifyingUser is None:
            oh.LastModifyingUser = oh.OwningUser
        if oh.LastModifyingApplication is None:
            oh.LastModifyingApplication = oh.OwningApplication
        if not oh.CreationDate:
            oh.CreationDate = now
    log.add("fix_owner_history", fields_repaired=changed)
    return changed


def merge_duplicate_types(f, log: Log):
    """Types with identical (class, Name) -> one keeper; rewire the rels."""
    groups = defaultdict(list)
    for t in f.by_type("IfcTypeObject"):
        groups[(t.is_a(), (t.Name or "").strip())].append(t)
    merged = 0
    for (cls, name), lst in groups.items():
        if len(lst) < 2:
            continue
        lst = sorted(lst, key=lambda t: t.id())
        keeper = lst[0]
        # gather all occurrences of every duplicate
        occurrences = []
        keeper_rel = None
        for t in lst:
            for rel in list(getattr(t, "Types", []) or []):
                if t is keeper and keeper_rel is None:
                    keeper_rel = rel
                    occurrences.extend(rel.RelatedObjects)
                else:
                    occurrences.extend(rel.RelatedObjects)
                    f.remove(rel)
        if keeper_rel is None and occurrences:
            keeper_rel = f.createIfcRelDefinesByType(
                _guid(), _oh(f), None, None, occurrences, keeper)
        elif keeper_rel is not None:
            # dedupe & assign
            seen, uniq = set(), []
            for o in occurrences:
                if o.id() not in seen:
                    seen.add(o.id()); uniq.append(o)
            keeper_rel.RelatedObjects = uniq
        for t in lst[1:]:
            try:
                _ue.remove_deep2(f, t)
            except Exception:
                f.remove(t)
            merged += 1
        log.add("merge_duplicate_types", cls=cls, name=name,
                merged_away=len(lst) - 1, keeper=f"#{keeper.id()}",
                occurrences=len(keeper_rel.RelatedObjects) if keeper_rel else 0)
    return merged


def _geometry_signature(rec):
    sig = []
    for it in rec["geometry"]["items"]:
        ext = tuple(round(x, 3) for x in sorted(it.get("extent", [0, 0, 0])))
        sig.append((ext, it.get("triangles", 0)))
    return tuple(sorted(sig))


def create_types_for_untyped(f, inventory, log: Log):
    """One shared type per (class, predefined, geometry signature) group of
    untyped elements. Naming: '<Class> <dims mm>' from the largest box."""
    groups = defaultdict(list)
    by_id = {r["step_id"]: r for r in inventory}
    for rec in inventory:
        if rec["type_id"]:
            continue
        key = (rec["class"], str(rec["predefined_type"]), _geometry_signature(rec))
        groups[key].append(rec)
    created = 0
    for (cls, pdt, sig), members in groups.items():
        tcls = type_class_for(f, cls)
        if not tcls:
            continue
        # a readable name from the biggest geometry item
        dims = ""
        exts = [sorted(it.get("extent", [])) for m in members[:1] for it in m["geometry"]["items"] if it.get("extent")]
        if exts:
            big = max(exts, key=lambda e: e[0] * e[1] * e[2] if len(e) == 3 else 0)
            if len(big) == 3:
                dims = " {:.0f}x{:.0f}x{:.0f}mm".format(big[2] * 1000, big[1] * 1000, big[0] * 1000)
        base = cls[3:] if cls.startswith("Ifc") else cls
        pretty = "".join((" " + ch if ch.isupper() else ch) for ch in base).strip()
        name = f"{pretty}{dims}"
        kwargs = dict(GlobalId=_guid(), OwnerHistory=_oh(f), Name=name)
        prods = [f.by_id(m["step_id"]) for m in members]
        # carry the occurrence PredefinedType when the type class supports it
        try:
            ent = f.create_entity(tcls, **kwargs)
        except Exception:
            ent = f.create_entity(tcls, GlobalId=_guid(), Name=name)
        pd = getattr(prods[0], "PredefinedType", None)
        if pd and hasattr(ent, "PredefinedType"):
            try:
                ent.PredefinedType = pd
            except Exception:
                pass
        f.createIfcRelDefinesByType(_guid(), _oh(f), None, None, prods, ent)
        created += 1
        log.add("create_shared_type", type=f"#{ent.id()} {tcls} '{name}'",
                occurrences=[p.Name for p in prods])
    return created


def _pset_signature(f, pset):
    props = []
    for pr in pset.HasProperties:
        if pr.is_a("IfcPropertySingleValue"):
            v = pr.NominalValue
            props.append((pr.Name, v.is_a() if v is not None else None,
                          None if v is None else (v.wrappedValue if hasattr(v, "wrappedValue") else str(v))))
        else:
            props.append((pr.Name, pr.is_a(), str(pr)))
    return (pset.Name, tuple(sorted(props, key=lambda x: str(x))))


def dedupe_psets_to_types(f, log: Log):
    """For each type, psets that are identical on EVERY occurrence move to the type."""
    moved = 0
    for rel in f.by_type("IfcRelDefinesByType"):
        typ = rel.RelatingType
        occs = list(rel.RelatedObjects)
        if len(occs) < 2:
            continue
        # occurrence -> {signature: (pset, defining rel)}
        per_occ = []
        for o in occs:
            d = {}
            for r in getattr(o, "IsDefinedBy", []) or []:
                if r.is_a("IfcRelDefinesByProperties") and r.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                    d[_pset_signature(f, r.RelatingPropertyDefinition)] = (r.RelatingPropertyDefinition, r)
            per_occ.append(d)
        if not per_occ or not per_occ[0]:
            continue
        common = set(per_occ[0])
        for d in per_occ[1:]:
            common &= set(d)
        for sig in common:
            keep_pset, _ = per_occ[0][sig]
            # attach to the type
            hps = list(getattr(typ, "HasPropertySets", None) or [])
            if keep_pset not in hps:
                hps.append(keep_pset)
                typ.HasPropertySets = hps
            # detach from all occurrences (delete their defining rels + spare psets)
            for i, d in enumerate(per_occ):
                pset, drel = d[sig]
                remaining = [o for o in drel.RelatedObjects if o != occs[i]]
                if remaining:
                    drel.RelatedObjects = remaining
                else:
                    f.remove(drel)
                    if pset is not keep_pset and not f.get_inverse(pset):
                        for pr in pset.HasProperties:
                            f.remove(pr)
                        f.remove(pset)
            moved += 1
            log.add("move_pset_to_type", type=f"#{typ.id()}", pset=sig[0], occurrences=len(occs))
    return moved


def handle_phantoms(f, inventory, phantoms, log: Log, remove=True,
                    clearance_as_space=False):
    """Remove (or convert to IfcSpace) phantom annotation solids."""
    removed_products, removed_items, spaces = 0, 0, 0
    storeys = f.by_type("IfcBuildingStorey")
    storey = storeys[0] if storeys else None
    by_id = {r["step_id"]: r for r in inventory}
    for fnd in phantoms["findings"]:
        if fnd["confidence"] != "high":
            log.add("phantom_left", element=fnd["name"], reasons=fnd["reasons"],
                    note="low confidence -- kept")
            continue
        prod = f.by_id(fnd["step_id"])
        rec = by_id.get(fnd["step_id"])
        if fnd["whole_product"]:
            g = rec["geometry"] if rec else None
            if clearance_as_space and g and g.get("all_boxes") and storey is not None:
                # convert to IfcSpace: reuse existing shape as-is (kept simple)
                sp = f.createIfcSpace(prod.GlobalId, _oh(f), prod.Name, prod.Description,
                                       getattr(prod, "ObjectType", None),
                                       prod.ObjectPlacement, prod.Representation,
                                       (prod.Name or "CLEARANCE"), "ELEMENT", "INTERNAL", None)
                # detach product from rels then remove product shell only
                for rel in f.get_inverse(prod):
                    if rel.is_a("IfcRelContainedInSpatialStructure"):
                        rel.RelatedElements = [e for e in rel.RelatedElements if e != prod]
                    elif rel.is_a("IfcRelDefinesByProperties"):
                        rel.RelatedObjects = [o for o in rel.RelatedObjects if o != prod] + [sp]
                # aggregate space to storey
                agg = None
                for r in getattr(storey, "IsDecomposedBy", []) or []:
                    agg = r
                    break
                if agg is None:
                    f.createIfcRelAggregates(_guid(), _oh(f), None, None, storey, [sp])
                else:
                    agg.RelatedObjects = list(agg.RelatedObjects) + [sp]
                f.remove(prod)
                spaces += 1
                log.add("phantom_to_space", name=fnd["name"], reasons=fnd["reasons"])
            elif remove:
                # remove containment refs and the product with its geometry
                for rel in f.get_inverse(prod):
                    if rel.is_a("IfcRelContainedInSpatialStructure"):
                        rest = [e for e in rel.RelatedElements if e != prod]
                        if rest:
                            rel.RelatedElements = rest
                        else:
                            f.remove(rel)
                    elif rel.is_a("IfcRelDefinesByProperties") or rel.is_a("IfcRelDefinesByType"):
                        rest = [o for o in rel.RelatedObjects if o != prod]
                        if rest:
                            rel.RelatedObjects = rest
                        else:
                            f.remove(rel)
                if prod.Representation:
                    for r in list(prod.Representation.Representations):
                        for it in list(r.Items):
                            remove_item_deep(f, it, log)
                        f.remove(r)
                    f.remove(prod.Representation)
                f.remove(prod)
                removed_products += 1
                log.add("phantom_removed", name=fnd["name"], cls=fnd["class"],
                        reasons=fnd["reasons"])
        else:
            # item-level phantoms inside an otherwise real element
            if not remove:
                continue
            for hit in fnd["items"]:
                strong = any(("annotation vocabulary" in r) or ("transparent" in r) for r in hit["reasons"])
                if not strong:
                    continue
                try:
                    it = f.by_id(hit["item_id"])
                except Exception:
                    continue
                for rep in f.get_inverse(it):
                    if rep.is_a("IfcShapeRepresentation"):
                        rep.Items = [i for i in rep.Items if i != it]
                remove_item_deep(f, it, log)
                removed_items += 1
                log.add("phantom_item_removed", element=fnd["name"],
                        item=hit["style_name"], reasons=hit["reasons"])
    return removed_products, removed_items, spaces


def convert_boxes_to_extrusions(f, inventory, body_ctx, log: Log):
    """Products whose whole tessellated geometry is exact boxes -> extrusions,
    with the product placement moved to the primary box base-centre."""
    converted_products, converted_boxes = 0, 0
    z = np.array([0.0, 0.0, 1.0])
    for rec in inventory:
        g = rec["geometry"]
        if not (g.get("all_boxes") and g.get("boxes")):
            continue
        prod = f.by_id(rec["step_id"])
        if prod is None or prod.Representation is None:
            continue
        boxes = g["boxes"]
        # primary = largest volume -> insertion point
        prim = max(boxes, key=lambda b: b["xdim"] * b["ydim"] * b["height"])
        T = matrix_of_frame(prim["origin"], prim["xdir"], z)   # in old product-local coords
        Tinv = np.linalg.inv(T)
        # new relative placement = old_rel @ T
        lp = prod.ObjectPlacement
        old_rel = rel_placement_matrix(lp) if lp is not None else np.eye(4)
        new_rel = old_rel @ T
        origin = new_rel[:3, 3]
        xd = new_rel[:3, 0]
        zd = new_rel[:3, 2]
        newpl = axis2placement(f, origin, xd, zd)
        if lp is None:
            prod.ObjectPlacement = f.createIfcLocalPlacement(None, newpl)
        else:
            lp.RelativePlacement = newpl
        # collect existing tessellated items + their styles, in order
        old_items = []
        for r in prod.Representation.Representations:
            for it in r.Items:
                if it.is_a("IfcTriangulatedFaceSet") or it.is_a("IfcPolygonalFaceSet"):
                    old_items.append((r, it))
        # build one extrusion per box, in the NEW local frame
        new_items = []
        # match boxes back to their source item for styling: re-decompose per item
        for r, it in old_items:
            pts, tris = bl.faceset_points_tris(it)
            iboxes, _ = bl.decompose_boxes(pts, tris)
            styles = styled_items_for(f, it)
            for b in iboxes:
                o_local = (Tinv @ np.array(b["origin"] + [1.0]))[:3]
                x_local = Tinv[:3, :3] @ np.array(b["xdir"])
                x_local[2] = 0.0
                n = np.linalg.norm(x_local)
                x_local = x_local / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])
                profile = f.createIfcRectangleProfileDef("AREA", None, None,
                                                        float(b["xdim"]), float(b["ydim"]))
                pos = axis2placement(f, o_local, x_local, z)
                solid = f.createIfcExtrudedAreaSolid(profile, pos,
                                                     f.createIfcDirection([0.0, 0.0, 1.0]),
                                                     float(b["height"]))
                for si in styles:
                    # clone the style assignment onto the new solid
                    f.createIfcStyledItem(solid, list(si.Styles), si.Name)
                new_items.append(solid)
                converted_boxes += 1
        # swap representation: one Body/SweptSolid rep replacing the old ones
        reps = list(prod.Representation.Representations)
        keep = []
        for r in reps:
            r.Items = [i for i in r.Items
                       if not (i.is_a("IfcTriangulatedFaceSet") or i.is_a("IfcPolygonalFaceSet"))]
            if r.Items:
                keep.append(r)
        ctx = body_ctx if body_ctx is not None else (reps[0].ContextOfItems if reps else None)
        newrep = f.createIfcShapeRepresentation(ctx, "Body", "SweptSolid", new_items)
        prod.Representation.Representations = keep + [newrep]
        # delete old facesets + point lists + orphaned reps
        for r, it in old_items:
            remove_item_deep(f, it, log)
        for r in reps:
            if r not in keep and not f.get_inverse(r):
                f.remove(r)
        converted_products += 1
        log.add("boxes_to_extrusions", element=rec["name"], boxes=len(boxes),
                insertion_point=[round(float(x), 4) for x in origin.tolist()],
                yaw_deg=round(math.degrees(math.atan2(xd[1], xd[0])), 2))
    return converted_products, converted_boxes


def contain_orphans(f, inventory, log: Log):
    orph = [f.by_id(i) for i in bl.spatial_audit(f, inventory)["orphan_element_ids"]]
    if not orph:
        return 0
    storeys = f.by_type("IfcBuildingStorey")
    if not storeys:
        st = f.createIfcBuildingStorey(_guid(), _oh(f), "Level 1", None, None,
                                        f.createIfcLocalPlacement(None, axis2placement(f, (0, 0, 0))),
                                        None, None, "ELEMENT", 0.0)
        bldgs = f.by_type("IfcBuilding")
        if bldgs:
            f.createIfcRelAggregates(_guid(), _oh(f), None, None, bldgs[0], [st])
        storeys = [st]
    st = storeys[0]
    rel = None
    for r in f.by_type("IfcRelContainedInSpatialStructure"):
        if r.RelatingStructure == st:
            rel = r
            break
    if rel is None:
        f.createIfcRelContainedInSpatialStructure(_guid(), _oh(f), None, None, orph, st)
    else:
        rel.RelatedElements = list(rel.RelatedElements) + orph
    log.add("contain_orphans", count=len(orph), storey=st.Name)
    return len(orph)


def body_context(f):
    for c in f.by_type("IfcGeometricRepresentationSubContext"):
        if (c.ContextIdentifier or "").lower() == "body":
            return c
    ctxs = [c for c in f.by_type("IfcGeometricRepresentationContext")
            if not c.is_a("IfcGeometricRepresentationSubContext") and (c.ContextType or "").lower() == "model"]
    return ctxs[0] if ctxs else None


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #

def summarize(f, path=None) -> dict:
    types = f.by_type("IfcTypeObject")
    prods = bl.element_products(f)
    tess = sum(1 for p in prods if p.Representation and any(
        i.is_a() in bl.TESSELLATED_ITEM
        for r in p.Representation.Representations for i in r.Items))
    return {
        "entities": len(list(f)),
        "elements": len(prods),
        "type_objects": len(types),
        "rel_defines_by_type": len(f.by_type("IfcRelDefinesByType")),
        "triangulated_facesets": len(f.by_type("IfcTriangulatedFaceSet")),
        "extruded_solids": len(f.by_type("IfcExtrudedAreaSolid")),
        "tessellated_elements": tess,
        "spaces": len(f.by_type("IfcSpace")),
        "property_sets": len(f.by_type("IfcPropertySet")),
        "identity_placements": sum(1 for p in prods
                                    if bl.is_identity(bl.compose_placement(p))),
        "size_bytes": os.path.getsize(path) if path and os.path.exists(path) else None,
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def harden(in_path: str, out_path: str, **opts) -> dict:
    """Rewrite ``in_path`` to ``out_path`` and return the action/diff result
    (what ``--report`` writes); ``opts`` are harden_analysed's switches."""
    f = ifcopenshell.open(in_path)
    return harden_analysed(in_path, out_path, bl.analyze(in_path, model=f), model=f, **opts)[0]


def harden_analysed(in_path: str, out_path: str, before_report: dict, *, model=None,
                    remove_phantoms=True, clearance_as_space=False, create_types=True,
                    extrusions=True) -> tuple:
    """``harden`` for a caller that already analysed the input (ifc_flow.py,
    #754): ``before_report`` is its full ``bridge_lib.analyze`` report (step
    ids are the file's own, so the surgery is identical) and ``model`` the
    already-open ``ifcopenshell.file`` it analysed, so the input is parsed
    and analysed once.  Returns ``(result, after_report)`` -- the action/diff
    result and the reopened output's full report, so that need not be
    analysed again either."""
    f = ifcopenshell.open(in_path) if model is None else model
    log = Log()
    before = summarize(f, in_path)
    rep0 = before_report              # audits drive the surgery
    inv = rep0["products"]
    before["duplicate_type_objects"] = rep0["types"]["duplicate_type_objects"]
    before["untyped_elements"] = rep0["types"]["products_untyped"]
    before["score"] = rep0["score"]["score"]
    before["tier"] = rep0["score"]["tier"]

    n_owner = fix_owner_history(f, log)
    n_merged = merge_duplicate_types(f, log)
    # phantom handling before geometry conversion (phantoms use the old inventory)
    ph_products, ph_items, ph_spaces = handle_phantoms(
        f, inv, rep0["phantoms"], log, remove=remove_phantoms,
        clearance_as_space=clearance_as_space)
    # re-inventory after removals (step ids of survivors are stable)
    survivors = [r for r in inv if _still_there(f, r["step_id"])]
    n_types_created = create_types_for_untyped(f, survivors, log) if create_types else 0
    n_prod_conv = n_box_conv = 0
    if extrusions:
        n_prod_conv, n_box_conv = convert_boxes_to_extrusions(f, survivors, body_context(f), log)
    n_psets_moved = dedupe_psets_to_types(f, log)
    n_orphans = contain_orphans(f, survivors, log)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    f.write(out_path)

    # reopen + verify
    f2 = ifcopenshell.open(out_path)
    after = summarize(f2, out_path)
    rep1 = bl.analyze(out_path, model=f2)
    after["duplicate_type_objects"] = rep1["types"]["duplicate_type_objects"]
    after["untyped_elements"] = rep1["types"]["products_untyped"]
    after["score"] = rep1["score"]["score"]
    after["tier"] = rep1["score"]["tier"]
    schema_after = rep1["schema"]

    # GlobalId preservation check for surviving products
    guids_before = {r["guid"] for r in inv}
    guids_after = {r["guid"] for r in rep1["products"]}
    preserved = len(guids_after & guids_before)

    result = {
        "input": os.path.abspath(in_path),
        "output": os.path.abspath(out_path),
        "before": before,
        "after": after,
        "diff": {k: (after.get(k), before.get(k)) and {"before": before.get(k), "after": after.get(k)}
                 for k in before if k in after},
        "actions": {
            "owner_history_fields_repaired": n_owner,
            "duplicate_types_merged": n_merged,
            "shared_types_created": n_types_created,
            "psets_moved_to_types": n_psets_moved,
            "phantom_products_removed": ph_products,
            "phantom_items_removed": ph_items,
            "phantom_converted_to_space": ph_spaces,
            "products_converted_to_extrusions": n_prod_conv,
            "boxes_converted": n_box_conv,
            "orphans_contained": n_orphans,
            "product_globalids_preserved": preserved,
            "products_before": len(inv),
            "products_after": len(rep1["products"]),
        },
        "schema_after": {"errors": schema_after.get("n_errors"),
                         "warnings": schema_after.get("n_warnings"),
                         "reopened": True},
        "log": log.entries,
    }
    return result, rep1


def _still_there(f, step_id) -> bool:
    try:
        e = f.by_id(step_id)
        return e is not None
    except Exception:
        return False


def print_diff(res: dict):
    b, a = res["before"], res["after"]
    print("harden_ifc: {} -> {}".format(os.path.basename(res["input"]), os.path.basename(res["output"])))
    print("=" * 78)
    keys = ["entities", "size_bytes", "elements", "type_objects", "duplicate_type_objects",
            "untyped_elements", "rel_defines_by_type", "triangulated_facesets",
            "tessellated_elements", "extruded_solids", "spaces", "property_sets",
            "identity_placements", "score", "tier"]
    print(f"  {'metric':28s} {'before':>28s}    {'after':>28s}")
    for k in keys:
        print(f"  {k:28s} {str(b.get(k)):>28s} -> {str(a.get(k)):>28s}")
    print()
    print("actions:")
    for k, v in res["actions"].items():
        print(f"  {k:36s} {v}")
    print()
    print(f"reopened OK, schema errors after = {res['schema_after']['errors']}, "
          f"warnings = {res['schema_after']['warnings']}")


def add_harden_args(ap: argparse.ArgumentParser) -> None:
    """The hardening switches, shared with ifc_flow.py (one option table)."""
    ap.add_argument("--keep-clearance-as-space", action="store_true",
                    help="convert axis-aligned box clearance volumes to IfcSpace instead of deleting")
    ap.add_argument("--no-remove-phantoms", action="store_true")
    ap.add_argument("--no-create-types", action="store_true",
                    help="do not synthesise shared types for untyped elements")
    ap.add_argument("--no-extrusions", action="store_true",
                    help="do not convert exact boxes to extrusions")


def harden_kwargs(args: argparse.Namespace) -> dict:
    """The parsed switches as ``harden`` / ``harden_analysed`` keyword arguments."""
    return {"remove_phantoms": not args.no_remove_phantoms,
            "clearance_as_space": args.keep_clearance_as_space,
            "create_types": not args.no_create_types,
            "extrusions": not args.no_extrusions}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--report", help="write the JSON action/diff report here")
    add_harden_args(ap)
    args = ap.parse_args(argv)
    if not os.path.isfile(args.input):
        print(f"error: no such file: {args.input}", file=sys.stderr)
        return 2
    res = harden(args.input, args.output, **harden_kwargs(args))
    print_diff(res)
    if args.report:
        with open(args.report, "w") as fh:
            json.dump(res, fh, indent=2, default=str)
        print(f"\nreport -> {args.report}")
    return 0 if res["schema_after"]["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

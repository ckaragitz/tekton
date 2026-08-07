#!/usr/bin/env python3
"""generate_ifc.py -- deterministic building-spec (JSON) -> IFC4 generator.

Usage:
    python generate_ifc.py --spec spec.json -o out.ifc [--validate]

Consumes the versioned building spec (see spec/building.schema.json in the
repo): levels/storeys, footprint auto-walls, explicit walls, floors, roofs
(flat), doors/windows with real voided openings, rooms -> IfcSpace ... PLUS
the electrical/MEP profile:

    "equipment": [
      {"kind": "panelboard" | "transformer" | "lightfixture" | "proxy",
       "name": "B-HG4", "level": "Level 1",
       "position": [x, y],          # metres, plan
       "rotationDeg": 90,            # about +Z
       "elevation": 1.067,           # base above the level (mounting height)
       "dims": {"w": 0.508, "d": 0.15, "h": 0.914},
       "ifcClass": "IfcElectricDistributionBoard", "predefinedType": "DISTRIBUTIONBOARD",
       "typeName": "Eaton PRL4 400A MB 42sp",
       "psets": {"PanelSchedule": {"Voltage": {"value": 480, "type": "voltage"},
                                    "BusRating": {"value": 400, "type": "current"},
                                    "Mounting": "Surface"}},
       "typePsets": {"Pset_ManufacturerTypeInformation": {"Manufacturer": "Eaton"}}}
    ]

Equipment is emitted the Tier-1 way: box extrusions with the correct IFC
class + predefined type, ONE shared type per (kind, typeName) whose geometry
lives once in an IfcRepresentationMap (occurrences are IfcMappedItems),
real placements (insertion point + yaw), typed property sets, spatial
containment, and clearances recorded as psets (never as solids).

Determinism: identical spec -> byte-identical file (GUIDs are derived from a
seed = hash of the spec; timestamps are fixed to the spec's issueDate).

Exit codes: 0 written (and validated when --validate), 1 validation
failed, 2 spec / IO error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import ifcopenshell
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.api.context
import ifcopenshell.api.project
import ifcopenshell.api.aggregate
import ifcopenshell.api.spatial
import ifcopenshell.api.geometry
import ifcopenshell.api.feature
import ifcopenshell.api.owner
import ifcopenshell.api.pset
import ifcopenshell.guid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GENERATOR_VERSION = "0.1.0"
GUID_NS = uuid.UUID("6f0e3b6a-3f1c-4d0a-9d1c-0f6a8b2e0f11")

# --------------------------------------------------------------------------- #
# equipment profile defaults
# --------------------------------------------------------------------------- #

EQUIP_DEFAULTS = {
    "panelboard": {"ifcClass": "IfcElectricDistributionBoard", "predefinedType": "DISTRIBUTIONBOARD",
                   "dims": {"w": 0.508, "d": 0.15, "h": 0.914}, "elevation": 1.067,
                   "typeName": "Panelboard"},
    "transformer": {"ifcClass": "IfcTransformer", "predefinedType": "VOLTAGE",
                    "dims": {"w": 0.61, "d": 0.51, "h": 0.76}, "elevation": 0.10,
                    "typeName": "Dry-type transformer"},
    "lightfixture": {"ifcClass": "IfcLightFixture", "predefinedType": "POINTSOURCE",
                     "dims": {"w": 0.6, "d": 0.6, "h": 0.1}, "elevation": 2.7,
                     "typeName": "Light fixture"},
    "switchgear": {"ifcClass": "IfcElectricDistributionBoard", "predefinedType": "SWITCHBOARD",
                   "dims": {"w": 0.9, "d": 0.6, "h": 2.3}, "elevation": 0.0,
                   "typeName": "Switchboard"},
    "proxy": {"ifcClass": "IfcBuildingElementProxy", "predefinedType": "NOTDEFINED",
              "dims": {"w": 1.0, "d": 1.0, "h": 1.0}, "elevation": 0.0,
              "typeName": "Generic equipment"},
}

# psets typed-measure vocabulary (mirrors the Design userData.ifc contract)
MEASURE = {
    "boolean": "IfcBoolean", "integer": "IfcInteger", "count": "IfcCountMeasure",
    "real": "IfcReal", "voltage": "IfcElectricVoltageMeasure",
    "current": "IfcElectricCurrentMeasure", "power": "IfcPowerMeasure",
    "length": "IfcLengthMeasure", "area": "IfcAreaMeasure", "volume": "IfcVolumeMeasure",
    "identifier": "IfcIdentifier", "text": "IfcText", "label": "IfcLabel",
    "frequency": "IfcFrequencyMeasure", "thermal": "IfcThermodynamicTemperatureMeasure",
}

DEFAULTS = {
    "storeyHeight": 3.0, "wallThickness": 0.2, "slabThickness": 0.25,
    "roofForm": "flat", "doorWidth": 0.9, "doorHeight": 2.1, "windowWidth": 1.2,
    "windowHeight": 1.2, "sillHeight": 0.9, "autoOpenings": True,
    "roomBounding": True,
}


# --------------------------------------------------------------------------- #
# spec normalisation
# --------------------------------------------------------------------------- #

def load_spec(path: str) -> dict:
    with open(path) as fh:
        spec = json.load(fh)
    if not isinstance(spec, dict):
        raise ValueError("spec must be a JSON object")
    ver = str(spec.get("specVersion", "0.1.0"))
    major = ver.split(".")[0]
    if major != "0":
        raise ValueError(f"unsupported specVersion major {ver} (this generator understands 0.x)")
    return spec


def normalize(spec: dict) -> dict:
    """Expand shorthand into an explicit intermediate model (IR)."""
    d = dict(DEFAULTS)
    d.update(spec.get("defaults") or {})
    proj = {"name": "Untitled Project", "number": "0001", "buildingName": "Building",
            "author": "tekton-ifc", "organisation": "tekton-ifc", "description": ""}
    proj.update(spec.get("project") or {})
    units = {"length": "m", "angle": "deg"}
    units.update(spec.get("units") or {})

    # ---- levels
    levels = []
    if spec.get("levels"):
        for i, lv in enumerate(spec["levels"]):
            lid = lv.get("id") or lv.get("name") or f"L{i+1}"
            levels.append({"id": lid, "name": lv.get("name") or lid,
                           "elevation": float(lv["elevation"]),
                           "storey": bool(lv.get("storey", True))})
    else:
        n = int(spec.get("storeys", 1) or 1)
        h = float(d["storeyHeight"])
        for i in range(n):
            levels.append({"id": f"L{i+1}", "name": f"Level {i+1}",
                           "elevation": i * h, "storey": True})
        if spec.get("footprint") and d.get("roofForm", "flat") not in (None, "none"):
            levels.append({"id": "RF", "name": "Roof", "elevation": n * h, "storey": False})
    levels.sort(key=lambda l: l["elevation"])
    storeys = [l for l in levels if l["storey"]]
    if not storeys:
        storeys = [levels[0]] if levels else [{"id": "L1", "name": "Level 1", "elevation": 0.0, "storey": True}]
        if not levels:
            levels = list(storeys)
    for i, s in enumerate(storeys):
        # storey height = next datum above (any level) else default
        above = [l["elevation"] for l in levels if l["elevation"] > s["elevation"] + 1e-6]
        s["height"] = (min(above) - s["elevation"]) if above else float(d["storeyHeight"])

    ir = {"defaults": d, "project": proj, "units": units, "levels": levels,
          "storeys": storeys, "footprint": spec.get("footprint"),
          "types": spec.get("types") or {},
          "walls": [], "openings": [], "floors": [], "roofs": [], "spaces": [],
          "equipment": [], "site": spec.get("site") or {}, "targets": spec.get("targets") or {}}

    def level_idx(ref, fallback=0):
        if ref is None:
            return fallback
        if isinstance(ref, int):
            return max(0, min(len(storeys) - 1, ref))
        for i, s in enumerate(storeys):
            if ref in (s["id"], s["name"]):
                return i
        # non-storey datum (e.g. 'RF') -> map by elevation to enclosing storey
        for l in levels:
            if ref in (l["id"], l["name"]):
                cand = [i for i, s in enumerate(storeys) if s["elevation"] <= l["elevation"] + 1e-6]
                return cand[-1] if cand else 0
        return fallback

    def level_elev(ref, fallback_idx=0):
        for l in levels:
            if ref in (l.get("id"), l.get("name")):
                return l["elevation"]
        return storeys[level_idx(ref, fallback_idx)]["elevation"]

    ir["level_idx"] = level_idx

    # ---- footprint auto walls (per storey)
    fp = spec.get("footprint")
    wt = float(d["wallThickness"])
    if fp:
        for si, s in enumerate(storeys):
            for i in range(len(fp)):
                p1, p2 = fp[i], fp[(i + 1) % len(fp)]
                ir["walls"].append({"id": f"auto-{i}@{s['id']}", "auto": i, "level": si,
                                    "start": [float(p1[0]), float(p1[1])],
                                    "end": [float(p2[0]), float(p2[1])],
                                    "thickness": wt, "height": s["height"],
                                    "type": d.get("wallType") or "Generic",
                                    "external": True})
    # ---- explicit walls (append; explicit id lookup)
    for w in spec.get("walls") or []:
        li = level_idx(w.get("level"))
        base = storeys[li]
        height = w.get("height")
        if not height:
            if w.get("topLevel") and w["topLevel"] != "unconnected":
                height = level_elev(w["topLevel"], li) - base["elevation"] + float(w.get("topOffset", 0))
            else:
                height = base["height"]
        thick = w.get("thickness")
        if not thick and w.get("type"):
            tdef = ((spec.get("types") or {}).get("walls") or {}).get(w["type"])
            if tdef and tdef.get("layers"):
                thick = sum(float(l["thickness"]) for l in tdef["layers"])
        thick = float(thick or wt)
        ir["walls"].append({"id": w.get("id") or f"wall-{len(ir['walls'])}", "auto": None,
                            "level": li, "start": [float(x) for x in w["start"]],
                            "end": [float(x) for x in w["end"]], "thickness": thick,
                            "height": float(height), "type": w.get("type") or d.get("wallType") or "Generic",
                            "baseOffset": float(w.get("baseOffset", 0)),
                            "external": (w.get("function", "exterior") == "exterior")})

    # ---- floors: explicit or one slab per storey from the footprint
    if spec.get("floors"):
        for fl in spec["floors"]:
            li = level_idx(fl.get("level"))
            ir["floors"].append({"id": fl.get("id") or f"floor-{len(ir['floors'])}", "level": li,
                                 "boundary": fl.get("boundary") or fp,
                                 "thickness": float(fl.get("thickness") or d["slabThickness"]),
                                 "offset": float(fl.get("levelOffset", 0))})
    elif fp:
        for si in range(len(storeys)):
            ir["floors"].append({"id": f"slab-{storeys[si]['id']}", "level": si, "boundary": fp,
                                 "thickness": float(d["slabThickness"]), "offset": 0.0})
    # ---- flat roof (all roof forms are emitted flat with a note)
    roofs = spec.get("roofs")
    if roofs:
        for rf in roofs:
            if rf.get("form", d.get("roofForm")) == "none":
                continue
            elev = level_elev(rf.get("level"), len(storeys) - 1) if rf.get("level") else \
                storeys[-1]["elevation"] + storeys[-1]["height"]
            ir["roofs"].append({"id": rf.get("id") or "roof", "elevation": float(elev) + float(rf.get("baseOffset", 0)),
                                "boundary": rf.get("boundary") or fp,
                                "thickness": float(rf.get("thickness") or d["slabThickness"]),
                                "form": rf.get("form", d.get("roofForm", "flat"))})
    elif fp and d.get("roofForm", "flat") not in (None, "none"):
        top = storeys[-1]
        ir["roofs"].append({"id": "roof", "elevation": top["elevation"] + top["height"],
                            "boundary": fp, "thickness": float(d["slabThickness"]),
                            "form": d.get("roofForm", "flat")})

    # ---- openings (doors/windows)
    for kind in ("doors", "windows"):
        for op in spec.get(kind) or []:
            ir["openings"].append({
                "kind": "Door" if kind == "doors" else "Window",
                "id": op.get("id"), "hostWall": op["hostWall"],
                "level": level_idx(op.get("level")),
                "offset": op.get("offset"), "fraction": op.get("fraction"),
                "width": float(op.get("width") or (d["doorWidth"] if kind == "doors" else d["windowWidth"])),
                "height": float(op.get("height") or (d["doorHeight"] if kind == "doors" else d["windowHeight"])),
                "sill": float(op.get("sill") if op.get("sill") is not None else (0.0 if kind == "doors" else d["sillHeight"])),
                "type": op.get("type"), "operation": op.get("operation"),
            })
    # auto entrance door
    if fp and d.get("autoOpenings", True) and not spec.get("doors"):
        ir["openings"].append({"kind": "Door", "id": "D-auto", "hostWall": "auto-0", "level": 0,
                               "offset": 1.0, "fraction": None, "width": float(d["doorWidth"]),
                               "height": float(d["doorHeight"]), "sill": 0.0, "type": None,
                               "operation": "SINGLE_SWING_LEFT"})

    # ---- rooms -> spaces
    for rm in (spec.get("rooms") or []) + (spec.get("spaces") or []):
        li = level_idx(rm.get("level"))
        boundary = rm.get("boundary") or fp
        if not boundary and rm.get("point") and fp:
            boundary = fp
        if not boundary:
            continue
        ir["spaces"].append({"id": rm.get("id") or f"space-{len(ir['spaces'])}",
                             "name": rm.get("name", "Room"), "number": rm.get("number"),
                             "level": li, "boundary": boundary,
                             "height": float(rm.get("height") or storeys[li]["height"]),
                             "occupancy": rm.get("occupancy"),
                             "psets": rm.get("psets") or {}})

    # ---- equipment (MEP profile)
    for eq in spec.get("equipment") or []:
        kind = str(eq.get("kind", "proxy")).lower()
        base = dict(EQUIP_DEFAULTS.get(kind, EQUIP_DEFAULTS["proxy"]))
        dims = dict(base["dims"])
        dims.update(eq.get("dims") or {})
        rec = {
            "kind": kind, "name": eq.get("name") or kind,
            "level": level_idx(eq.get("level")),
            "position": [float(x) for x in (eq.get("position") or [0.0, 0.0])[:2]],
            "rotationDeg": float(eq.get("rotationDeg", 0.0)),
            "elevation": float(eq.get("elevation", base["elevation"])),
            "dims": {k: float(dims[k]) for k in ("w", "d", "h")},
            "ifcClass": eq.get("ifcClass") or base["ifcClass"],
            "predefinedType": eq.get("predefinedType") or base["predefinedType"],
            "typeName": eq.get("typeName") or base["typeName"],
            "description": eq.get("description"), "tag": eq.get("tag") or eq.get("name"),
            "psets": eq.get("psets") or {}, "typePsets": eq.get("typePsets") or {},
        }
        ir["equipment"].append(rec)
    return ir


# --------------------------------------------------------------------------- #
# determinism helpers
# --------------------------------------------------------------------------- #

class SeededGuids:
    def __init__(self, seed: str):
        self.seed = seed
        self.i = 0

    def __call__(self, *_a, **_k):
        g = ifcopenshell.guid.compress(uuid.uuid5(GUID_NS, f"{self.seed}:{self.i}").hex)
        self.i += 1
        return g


def spec_seed(spec: dict) -> str:
    blob = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha1(blob).hexdigest()[:16]


def epoch_from_spec(spec: dict) -> int:
    iso = (spec.get("project") or {}).get("issueDate")
    if iso:
        try:
            return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            pass
    return 1767225600  # 2026-01-01T00:00:00Z


# --------------------------------------------------------------------------- #
# low-level geometry helpers
# --------------------------------------------------------------------------- #

def _axis2p3d(f, origin, xdir=(1.0, 0.0, 0.0), zdir=(0.0, 0.0, 1.0)):
    return f.createIfcAxis2Placement3D(
        f.createIfcCartesianPoint([float(x) for x in origin]),
        f.createIfcDirection([float(x) for x in zdir]),
        f.createIfcDirection([float(x) for x in xdir]))


def _local_placement(f, rel_to, origin, xdir=(1.0, 0.0, 0.0)):
    return f.createIfcLocalPlacement(rel_to, _axis2p3d(f, origin, xdir))


def box_extrusion(f, w, d_, h, base_origin=(0.0, 0.0, 0.0), xdir=(1.0, 0.0, 0.0)):
    """IfcExtrudedAreaSolid of a w(x) x d(y) x h(z) box with base-centre at
    base_origin (local), extruding along +Z."""
    prof = f.createIfcRectangleProfileDef("AREA", None, None, float(w), float(d_))
    return f.createIfcExtrudedAreaSolid(prof, _axis2p3d(f, base_origin, xdir),
                                        f.createIfcDirection([0.0, 0.0, 1.0]), float(h))


def polygon_extrusion(f, poly2d, height, base_z=0.0):
    pts = [f.createIfcCartesianPoint([float(x), float(y)]) for x, y in poly2d]
    pts.append(pts[0])
    pl = f.createIfcPolyline(pts)
    prof = f.createIfcArbitraryClosedProfileDef("AREA", None, pl)
    return f.createIfcExtrudedAreaSolid(prof, _axis2p3d(f, (0.0, 0.0, float(base_z))),
                                        f.createIfcDirection([0.0, 0.0, 1.0]), float(height))


def shape_rep(f, ctx, items, ident="Body", rtype="SweptSolid"):
    rep = f.createIfcShapeRepresentation(ctx, ident, rtype, items)
    return f.createIfcProductDefinitionShape(None, None, [rep])


def add_pset(f, oh, obj, name, props: dict, target_type=False):
    """Create an IfcPropertySet from {prop: scalar | {value,type}} and attach."""
    if not props:
        return None
    hp = []
    for k, v in props.items():
        mt = None
        if isinstance(v, dict) and "value" in v:
            mt = MEASURE.get(str(v.get("type", "label")).lower(), "IfcLabel")
            val = v["value"]
        else:
            val = v
            if isinstance(val, bool):
                mt = "IfcBoolean"
            elif isinstance(val, int):
                mt = "IfcInteger"
            elif isinstance(val, float):
                mt = "IfcReal"
            else:
                mt, val = "IfcLabel", str(val)
        if mt == "IfcBoolean":
            val = bool(val)
        elif mt in ("IfcInteger", "IfcCountMeasure"):
            val = int(val)
        elif mt in ("IfcLabel", "IfcText", "IfcIdentifier"):
            val = str(val)
        else:
            val = float(val)
        hp.append(f.createIfcPropertySingleValue(str(k), None, f.create_entity(mt, val), None))
    pset = f.createIfcPropertySet(ifcopenshell.guid.new(), oh, str(name), None, hp)
    if target_type:
        cur = list(getattr(obj, "HasPropertySets", None) or [])
        obj.HasPropertySets = cur + [pset]
    else:
        f.createIfcRelDefinesByProperties(ifcopenshell.guid.new(), oh, None, None, [obj], pset)
    return pset


# --------------------------------------------------------------------------- #
# builder
# --------------------------------------------------------------------------- #

def build(spec: dict, spec_path: str = "spec.json") -> tuple[ifcopenshell.file, dict]:
    ir = normalize(spec)
    guids = SeededGuids(spec_seed(spec))
    ifcopenshell.guid.new = guids            # deterministic GlobalIds everywhere
    epoch = epoch_from_spec(spec)

    f = ifcopenshell.api.project.create_file(version="IFC4")
    stats = {"walls": 0, "slabs": 0, "roofs": 0, "doors": 0, "windows": 0,
             "spaces": 0, "equipment": 0, "types": 0, "notes": []}

    # ---- ownership
    proj = ir["project"]
    person = ifcopenshell.api.owner.add_person(
        f, identification=str(proj.get("author") or "tekton-ifc"),
        family_name="Generator", given_name=str(proj.get("author") or "tekton-ifc"))
    org = ifcopenshell.api.owner.add_organisation(
        f, identification=str(proj.get("organisation") or "tekton-ifc"),
        name=str(proj.get("organisation") or "tekton-ifc"))
    user = ifcopenshell.api.owner.add_person_and_organisation(f, person=person, organisation=org)
    app = ifcopenshell.api.owner.add_application(
        f, application_developer=org, version=GENERATOR_VERSION,
        application_full_name="tekton-ifc generate_ifc",
        application_identifier="tekton-ifc")
    ifcopenshell.api.owner.settings.get_user = lambda ifc: user
    ifcopenshell.api.owner.settings.get_application = lambda ifc: app

    def create(cls, **kw):
        return ifcopenshell.api.root.create_entity(f, ifc_class=cls, **kw)

    contain_rels = {}   # storey step id -> IfcRelContainedInSpatialStructure

    def contain(products, storey):
        """Deterministic spatial containment (avoids the API's set-ordered
        placement rewrites, which make output ids vary between runs)."""
        rel = contain_rels.get(storey.id())
        if rel is None:
            rel = f.createIfcRelContainedInSpatialStructure(
                ifcopenshell.guid.new(), oh, None, None, list(products), storey)
            contain_rels[storey.id()] = rel
        else:
            rel.RelatedElements = list(rel.RelatedElements) + list(products)

    project = create("IfcProject", name=str(proj.get("name")))
    if proj.get("description"):
        project.Description = str(proj["description"])
    project.LongName = str(proj.get("number", ""))
    ifcopenshell.api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})
    ua = f.by_type("IfcUnitAssignment")[0]
    extra = [
        f.createIfcSIUnit(None, "PLANEANGLEUNIT", None, "RADIAN"),
        f.createIfcSIUnit(None, "ELECTRICVOLTAGEUNIT", None, "VOLT"),
        f.createIfcSIUnit(None, "ELECTRICCURRENTUNIT", None, "AMPERE"),
        f.createIfcSIUnit(None, "POWERUNIT", None, "WATT"),
        f.createIfcSIUnit(None, "FREQUENCYUNIT", None, "HERTZ"),
    ]
    have = {u.UnitType for u in ua.Units if u.is_a("IfcSIUnit") or u.is_a("IfcConversionBasedUnit")}
    ua.Units = list(ua.Units) + [u for u in extra if u.UnitType not in have]

    model = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)

    site = create("IfcSite", name=str(ir["site"].get("name", "Site")))
    building = create("IfcBuilding", name=str(proj.get("buildingName", "Building")))
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)
    oh = f.by_type("IfcOwnerHistory")[0]

    # ---- shared architectural types (one per distinct type name)
    arch_types = {}   # (type entity name, name) -> {"type": ent, "occ": []}

    def get_type(tcls: str, name: str, predefined=None):
        key = (tcls, name)
        if key not in arch_types:
            ent = f.create_entity(tcls, GlobalId=ifcopenshell.guid.new(), OwnerHistory=oh, Name=str(name))
            if predefined and hasattr(ent, "PredefinedType"):
                try:
                    ent.PredefinedType = predefined
                except Exception:
                    pass
            # mandatory sub-attributes on some type classes
            if tcls == "IfcDoorType":
                ent.OperationType = "SINGLE_SWING_LEFT"
                ent.ParameterTakesPrecedence = False
            elif tcls == "IfcWindowType":
                ent.PartitioningType = "SINGLE_PANEL"
                ent.ParameterTakesPrecedence = False
            arch_types[key] = {"type": ent, "occ": []}
            stats["types"] += 1
        return arch_types[key]

    # ---- storeys
    storey_ents = []
    for s in ir["storeys"]:
        st = create("IfcBuildingStorey", name=s["name"])
        st.Elevation = s["elevation"]
        ifcopenshell.api.geometry.edit_object_placement(
            f, product=st, matrix=np.array(
                [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, s["elevation"]], [0, 0, 0, 1]], float))
        ifcopenshell.api.aggregate.assign_object(f, products=[st], relating_object=building)
        storey_ents.append(st)

    # ---- walls
    wall_ent = {}      # wall id -> (entity, wall record)
    auto_by_level = {}  # (auto index, level idx) -> id
    for w in ir["walls"]:
        st = storey_ents[w["level"]]
        p1, p2 = np.array(w["start"], float), np.array(w["end"], float)
        if np.linalg.norm(p2 - p1) < 1e-6:
            continue
        went = create("IfcWall", name=w["id"], predefined_type="STANDARD")
        rep = ifcopenshell.api.geometry.create_2pt_wall(
            f, element=went, context=body, p1=tuple(p1), p2=tuple(p2),
            elevation=st.Elevation + w.get("baseOffset", 0.0),
            height=w["height"], thickness=w["thickness"])
        ifcopenshell.api.geometry.assign_representation(f, product=went, representation=rep)
        contain([went], st)
        went.ObjectType = str(w["type"])
        p = ifcopenshell.api.pset.add_pset(f, product=went, name="Pset_WallCommon")
        ifcopenshell.api.pset.edit_pset(f, pset=p, properties={
            "IsExternal": bool(w.get("external", True)), "LoadBearing": True,
            "Reference": str(w["type"])})
        wall_ent[w["id"]] = (went, w)
        if w.get("auto") is not None:
            auto_by_level[(w["auto"], w["level"])] = w["id"]
        get_type("IfcWallType", f"{w['type']} {int(round(w['thickness']*1000))}mm", "STANDARD")["occ"].append(went)
        stats["walls"] += 1

    # ---- floors + roof
    for fl in ir["floors"]:
        st = storey_ents[fl["level"]]
        slab = create("IfcSlab", name=fl["id"], predefined_type="FLOOR")
        rep = ifcopenshell.api.geometry.add_slab_representation(
            f, context=body, depth=fl["thickness"], polyline=[tuple(map(float, p)) for p in fl["boundary"]])
        ifcopenshell.api.geometry.assign_representation(f, product=slab, representation=rep)
        z = st.Elevation - fl["thickness"] + fl.get("offset", 0.0)
        ifcopenshell.api.geometry.edit_object_placement(
            f, product=slab, matrix=np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, z], [0, 0, 0, 1]], float))
        contain([slab], st)
        get_type("IfcSlabType", f"Slab {int(round(fl['thickness']*1000))}mm", "FLOOR")["occ"].append(slab)
        stats["slabs"] += 1
    for rf in ir["roofs"]:
        st = storey_ents[-1]
        roof = create("IfcRoof", name=rf["id"], predefined_type="FLAT_ROOF")
        rep = ifcopenshell.api.geometry.add_slab_representation(
            f, context=body, depth=rf["thickness"], polyline=[tuple(map(float, p)) for p in rf["boundary"]])
        ifcopenshell.api.geometry.assign_representation(f, product=roof, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(
            f, product=roof, matrix=np.array(
                [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, rf["elevation"]], [0, 0, 0, 1]], float))
        contain([roof], st)
        if rf.get("form") not in ("flat", None, "none"):
            stats["notes"].append(f"roof '{rf['id']}': form '{rf['form']}' emitted as flat (pitched roofs pending)")
        stats["roofs"] += 1

    # ---- openings (doors / windows) with real voids
    for op in ir["openings"]:
        hw = op["hostWall"]
        wid = None
        if hw.startswith("auto-"):
            try:
                idx = int(hw.split("-")[1].split("@")[0])
            except ValueError:
                idx = 0
            wid = auto_by_level.get((idx, op["level"]))
        if wid is None:
            wid = hw
        if wid not in wall_ent:
            stats["notes"].append(f"{op['kind']} '{op.get('id')}': host wall '{hw}' not found - skipped")
            continue
        went, wrec = wall_ent[wid]
        st = storey_ents[wrec["level"]]
        p1, p2 = np.array(wrec["start"], float), np.array(wrec["end"], float)
        d_ = p2 - p1
        L = float(np.linalg.norm(d_))
        u = d_ / L
        if op.get("fraction") is not None:
            off = float(op["fraction"]) * L - op["width"] / 2.0
        else:
            off = float(op.get("offset") or 0.0)
        off = max(0.0, min(off, max(0.0, L - op["width"])))
        origin = p1 + u * off
        z = st.Elevation + op["sill"]
        eps = 0.05
        n = np.array([-u[1], u[0]])
        o2 = origin - n * eps
        ang = math.atan2(u[1], u[0])
        m = np.array([[math.cos(ang), -math.sin(ang), 0, o2[0]],
                      [math.sin(ang), math.cos(ang), 0, o2[1]],
                      [0, 0, 1, z], [0, 0, 0, 1]], float)
        opening = create("IfcOpeningElement", name=f"{op['kind']}-Opening", predefined_type="OPENING")
        orep = ifcopenshell.api.geometry.add_wall_representation(
            f, context=body, length=op["width"], height=op["height"],
            thickness=wrec["thickness"] + 2 * eps)
        ifcopenshell.api.geometry.assign_representation(f, product=opening, representation=orep)
        ifcopenshell.api.geometry.edit_object_placement(f, product=opening, matrix=m)
        ifcopenshell.api.feature.add_feature(f, feature=opening, element=went)
        elem = create("IfcDoor" if op["kind"] == "Door" else "IfcWindow",
                      name=op.get("id") or op["kind"])
        elem.OverallWidth = op["width"]
        elem.OverallHeight = op["height"]
        if op["kind"] == "Door":
            elem.PredefinedType = "DOOR"
            if op.get("operation"):
                try:
                    elem.OperationType = op["operation"]
                except Exception:
                    pass
            frep = ifcopenshell.api.geometry.add_door_representation(
                f, context=body, overall_width=op["width"], overall_height=op["height"])
            stats["doors"] += 1
            tname = op.get("type") or f"Door {int(round(op['width']*1000))} x {int(round(op['height']*1000))}mm"
            get_type("IfcDoorType", str(tname), "DOOR")["occ"].append(elem)
        else:
            elem.PredefinedType = "WINDOW"
            frep = ifcopenshell.api.geometry.add_window_representation(
                f, context=body, overall_width=op["width"], overall_height=op["height"])
            stats["windows"] += 1
            tname = op.get("type") or f"Window {int(round(op['width']*1000))} x {int(round(op['height']*1000))}mm"
            get_type("IfcWindowType", str(tname), "WINDOW")["occ"].append(elem)
        ifcopenshell.api.geometry.assign_representation(f, product=elem, representation=frep)
        m2 = m.copy()
        m2[0:2, 3] = origin
        ifcopenshell.api.geometry.edit_object_placement(f, product=elem, matrix=m2)
        ifcopenshell.api.feature.add_filling(f, opening=opening, element=elem)
        contain([elem], st)

    # ---- spaces (rooms)
    for sp in ir["spaces"]:
        st = storey_ents[sp["level"]]
        space = create("IfcSpace", name=str(sp["name"]))
        space.LongName = str(sp["name"])
        space.CompositionType = "ELEMENT"
        space.PredefinedType = "SPACE"
        if sp.get("number"):
            space.Name = str(sp["number"])
        solid = polygon_extrusion(f, sp["boundary"], sp["height"], base_z=0.0)
        space.Representation = shape_rep(f, body, [solid], "Body", "SweptSolid")
        space.ObjectPlacement = _local_placement(f, st.ObjectPlacement, (0.0, 0.0, 0.0))
        ifcopenshell.api.aggregate.assign_object(f, products=[space], relating_object=st)
        props = {"Reference": str(sp["name"]), "IsExternal": False}
        add_pset(f, oh, space, "Pset_SpaceCommon", props)
        if sp.get("occupancy"):
            add_pset(f, oh, space, "Pset_SpaceOccupancyRequirements",
                     {"OccupancyType": str(sp["occupancy"])})
        for pname, pprops in (sp.get("psets") or {}).items():
            add_pset(f, oh, space, pname, pprops)
        stats["spaces"] += 1

    # ---- equipment: shared types by (kind, typeName), mapped-item instancing
    type_cache = {}   # (ifcClass, typeName, dims tuple) -> (type entity, repmap)
    equip_by_level = {}   # storey idx -> [products]
    for eq in ir["equipment"]:
        w, dd, h = eq["dims"]["w"], eq["dims"]["d"], eq["dims"]["h"]
        cls = eq["ifcClass"]
        tkey = (cls, eq["typeName"], round(w, 6), round(dd, 6), round(h, 6))
        if tkey not in type_cache:
            # type geometry once, in a representation map (origin = base-centre)
            solid = box_extrusion(f, w, dd, h)
            trep = f.createIfcShapeRepresentation(body, "Body", "SweptSolid", [solid])
            rmap = f.createIfcRepresentationMap(_axis2p3d(f, (0.0, 0.0, 0.0)), trep)
            tcls = cls + "Type"
            try:
                tent = f.create_entity(tcls, GlobalId=ifcopenshell.guid.new(), OwnerHistory=oh,
                                       Name=str(eq["typeName"]))
            except Exception:
                tent = f.create_entity("IfcTypeProduct", GlobalId=ifcopenshell.guid.new(),
                                       OwnerHistory=oh, Name=str(eq["typeName"]))
            tent.RepresentationMaps = [rmap]
            if hasattr(tent, "PredefinedType") and eq.get("predefinedType"):
                try:
                    tent.PredefinedType = eq["predefinedType"]
                except Exception:
                    pass
            # type property sets: manufacturer info + nominal dims
            add_pset(f, oh, tent, "Pset_ManufacturerTypeInformation" if not eq["typePsets"] else
                     list(eq["typePsets"].keys())[0], (eq["typePsets"] or {}).get(
                         "Pset_ManufacturerTypeInformation",
                         {"ModelLabel": str(eq["typeName"])}) if not eq["typePsets"] else
                     eq["typePsets"][list(eq["typePsets"].keys())[0]], target_type=True)
            for extra_name, extra_props in list((eq["typePsets"] or {}).items())[1:]:
                add_pset(f, oh, tent, extra_name, extra_props, target_type=True)
            add_pset(f, oh, tent, "revitbridge_Dimensions",
                     {"Width": {"value": w, "type": "length"},
                      "Depth": {"value": dd, "type": "length"},
                      "Height": {"value": h, "type": "length"}}, target_type=True)
            type_cache[tkey] = {"type": tent, "map": rmap, "occurrences": []}
            stats["types"] += 1
        tinfo = type_cache[tkey]

        st = storey_ents[eq["level"]]
        ent = create(cls, name=str(eq["name"]))
        if hasattr(ent, "PredefinedType") and eq.get("predefinedType"):
            try:
                ent.PredefinedType = eq["predefinedType"]
            except Exception:
                stats["notes"].append(f"{eq['name']}: predefined type {eq['predefinedType']} not valid for {cls}")
        ent.ObjectType = str(eq["typeName"])
        ent.Tag = str(eq.get("tag") or eq["name"])
        if eq.get("description"):
            ent.Description = str(eq["description"])
        # occurrence geometry: a mapped item onto the shared type geometry
        op3 = f.createIfcCartesianTransformationOperator3D(None, None,
                                                          f.createIfcCartesianPoint([0.0, 0.0, 0.0]),
                                                          1.0, None)
        mitem = f.createIfcMappedItem(tinfo["map"], op3)
        ent.Representation = shape_rep(f, body, [mitem], "Body", "MappedRepresentation")
        # real placement: insertion point + yaw, relative to the storey
        yaw = math.radians(eq["rotationDeg"])
        xdir = (math.cos(yaw), math.sin(yaw), 0.0)
        ent.ObjectPlacement = _local_placement(
            f, st.ObjectPlacement,
            (eq["position"][0], eq["position"][1], eq["elevation"]), xdir)
        equip_by_level.setdefault(eq["level"], []).append(ent)
        tinfo["occurrences"].append(ent)
        # occurrence psets (typed measures)
        for pname, pprops in (eq["psets"] or {}).items():
            add_pset(f, oh, ent, pname, pprops)
        stats["equipment"] += 1
    for tkey, ti in type_cache.items():
        f.createIfcRelDefinesByType(ifcopenshell.guid.new(), oh, None, None,
                                     ti["occurrences"], ti["type"])
    for li, prods in equip_by_level.items():
        contain(prods, storey_ents[li])
    for key, ti in arch_types.items():
        if ti["occ"]:
            f.createIfcRelDefinesByType(ifcopenshell.guid.new(), oh, None, None, ti["occ"], ti["type"])

    unify_owner_history(f, epoch)
    return f, stats


def unify_owner_history(f, epoch: int):
    """The ifcopenshell API may spawn several IfcOwnerHistory objects; keep
    one, retarget everything to it and stamp deterministic dates."""
    ohs = f.by_type("IfcOwnerHistory")
    if not ohs:
        return
    keep = ohs[0]
    for extra in ohs[1:]:
        for ent in f.get_inverse(extra):
            for i, attr in enumerate(ent):
                if attr == extra:
                    ent[i] = keep
        f.remove(extra)
    keep.CreationDate = epoch
    keep.LastModifiedDate = epoch
    keep.ChangeAction = "ADDED"
    keep.State = "READWRITE"


def canonicalise(f):
    """Sort every unordered aggregate the API filled from a set so output is
    order-stable across runs (needed for byte determinism)."""
    def key(e):
        return (getattr(e, "GlobalId", None) or "", e.is_a(), e.id())
    for rel in f.by_type("IfcRelationship"):
        for attr in ("RelatedElements", "RelatedObjects", "RelatedBuildings"):
            if hasattr(rel, attr):
                val = getattr(rel, attr)
                if isinstance(val, tuple) and val:
                    setattr(rel, attr, sorted(val, key=key))
    for ua in f.by_type("IfcUnitAssignment"):
        ua.Units = sorted(ua.Units, key=lambda u: (u.is_a(), str(getattr(u, "UnitType", "")),
                                                    str(getattr(u, "Name", "")), u.id()))


def write_deterministic(f, path: str, spec: dict, spec_path: str):
    epoch = epoch_from_spec(spec)
    ts = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    canonicalise(f)
    proj = spec.get("project") or {}
    try:
        h = f.header
        # spec-derived (not path-derived) so identical spec => identical bytes
        num = str(proj.get("number") or "model").strip().replace(" ", "_")
        h.file_name.name = f"{num}.ifc"
        h.file_name.time_stamp = ts
        h.file_name.author = (str(proj.get("author") or "tekton-ifc"),)
        h.file_name.organization = (str(proj.get("organisation") or "tekton-ifc"),)
        h.file_name.preprocessor_version = "tekton-ifc generate_ifc " + GENERATOR_VERSION
        h.file_name.originating_system = "tekton-ifc generate_ifc " + GENERATOR_VERSION
        h.file_name.authorization = "tekton-ifc"
        h.file_description.description = ("ViewDefinition [DesignTransferView]",)
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    f.write(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True, help="building spec JSON")
    ap.add_argument("-o", "--output", required=True, help="output .ifc path")
    ap.add_argument("--validate", action="store_true",
                    help="after writing, run the tekton-ifc validator and print the summary")
    args = ap.parse_args(argv)
    try:
        spec = load_spec(args.spec)
    except Exception as e:
        print(f"error: bad spec: {e}", file=sys.stderr)
        return 2
    t0 = time.time()
    f, stats = build(spec, args.spec)
    write_deterministic(f, args.output, spec, args.spec)
    print(f"generate_ifc: wrote {args.output} ({os.path.getsize(args.output)} bytes, "
          f"{len(list(f))} entities) in {time.time()-t0:.2f}s")
    print("  emitted: " + ", ".join(f"{k}={v}" for k, v in stats.items() if k != "notes"))
    for n in stats["notes"]:
        print("  note: " + n)
    if args.validate:
        import bridge_lib
        rep = bridge_lib.analyze(args.output)
        print()
        print(bridge_lib.human_summary(rep))
        if rep["schema"].get("n_errors"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

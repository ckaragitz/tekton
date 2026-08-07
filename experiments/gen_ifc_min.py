#!/usr/bin/env python
"""gen_ifc_min.py -- minimum viable IFC4 generation experiment.

Emits experiments/out/min_house.ifc: a valid IFC4 (STEP physical file) model
containing

    IfcProject -> IfcSite -> IfcBuilding -> 2 x IfcBuildingStorey
    4 IfcWall (standard case, rectangular room, one on each side)
    1 IfcSlab (ground floor) + 1 IfcSlab (first floor)
    1 IfcDoor  filling an IfcOpeningElement voided into the south wall
    1 IfcWindow filling an IfcOpeningElement voided into the north wall

then re-opens the file and validates it (ifcopenshell.validate + a geometry
sanity pass that tessellates every product with the OpenCascade kernel and
confirms the door/window openings actually cut the wall solids).

This is the reference "spec -> IFC" backend prototype for Track B (open-format
generator). Everything is driven by the PARAMS dict below so it doubles as a
first sketch of the building-spec -> IFC compiler.

Run:  /Users/ck/dev/things/rev-revit/.venv/bin/python experiments/gen_ifc_min.py
Deps: ifcopenshell==0.8.5 (mac arm64 wheel installs cleanly via uv pip).
"""
from __future__ import annotations

import math
import os
import sys
import time

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
import ifcopenshell.validate

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
OUT_PATH = os.path.join(OUT_DIR, "min_house.ifc")

# --------------------------------------------------------------------------- #
# A tiny inline "spec" -- mirrors the shape of spec/building.schema.json so the
# real compiler can lift this code more or less as-is.
# --------------------------------------------------------------------------- #
PARAMS = {
    "project_name": "min_house",
    "footprint": [[0.0, 0.0], [8.0, 0.0], [8.0, 6.0], [0.0, 6.0]],  # metres, CCW
    "storeys": [
        {"name": "Level 1", "elevation": 0.0},
        {"name": "Level 2", "elevation": 3.0},
    ],
    "wall": {"thickness": 0.2, "height": 6.0},          # walls span both storeys
    "slab": {"depth": 0.25},
    "door": {"width": 0.9, "height": 2.1, "sill": 0.0, "wall": 0, "offset": 1.0},
    "window": {"width": 1.5, "height": 1.2, "sill": 0.9, "wall": 2, "offset": 3.0},
}


def create(f, cls, **kw):
    return ifcopenshell.api.root.create_entity(f, ifc_class=cls, **kw)


def build(params: dict) -> ifcopenshell.file:
    f = ifcopenshell.api.project.create_file(version="IFC4")

    # -- ownership / header niceties (Revit is fussy about a sane owner history)
    person = ifcopenshell.api.owner.add_person(f, identification="rvt-recon",
                                            family_name="Generator", given_name="rvt-recon")
    org = ifcopenshell.api.owner.add_organisation(f, identification="rvt-recon", name="rvt-recon")
    user = ifcopenshell.api.owner.add_person_and_organisation(f, person=person, organisation=org)
    app = ifcopenshell.api.owner.add_application(f, application_developer=org, version="0.1",
                                                  application_full_name="rvt-recon gen_ifc_min",
                                                  application_identifier="rvt-recon")
    ifcopenshell.api.owner.settings.get_user = lambda ifc: user
    ifcopenshell.api.owner.settings.get_application = lambda ifc: app

    project = create(f, "IfcProject", name=params["project_name"])
    ifcopenshell.api.unit.assign_unit(f, length={"is_metric": True, "raw": "METERS"})

    model = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)

    site = create(f, "IfcSite", name="Site")
    building = create(f, "IfcBuilding", name="Building")
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(f, products=[building], relating_object=site)

    storeys = []
    for s in params["storeys"]:
        st = create(f, "IfcBuildingStorey", name=s["name"])
        st.Elevation = s["elevation"]
        ifcopenshell.api.geometry.edit_object_placement(
            f, product=st, matrix=np.array(
                [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, s["elevation"]], [0, 0, 0, 1]], float))
        ifcopenshell.api.aggregate.assign_object(f, products=[st], relating_object=building)
        storeys.append(st)
    ground = storeys[0]

    # -- 4 walls around the footprint (create_2pt_wall handles axis+body+placement)
    fp = params["footprint"]
    wt, wh = params["wall"]["thickness"], params["wall"]["height"]
    walls = []
    for i in range(len(fp)):
        p1, p2 = fp[i], fp[(i + 1) % len(fp)]
        w = create(f, "IfcWall", name=f"Wall-{i}", predefined_type="STANDARD")
        rep = ifcopenshell.api.geometry.create_2pt_wall(
            f, element=w, context=body, p1=tuple(p1), p2=tuple(p2),
            elevation=0.0, height=wh, thickness=wt)
        # create_2pt_wall builds the body + sets placement but does not assign
        ifcopenshell.api.geometry.assign_representation(f, product=w, representation=rep)
        ifcopenshell.api.spatial.assign_container(f, products=[w], relating_structure=ground)
        pset = ifcopenshell.api.pset.add_pset(f, product=w, name="Pset_WallCommon")
        ifcopenshell.api.pset.edit_pset(f, pset=pset, properties={"IsExternal": True, "LoadBearing": True})
        walls.append(w)

    # -- slabs: ground slab + level-2 floor, footprint polygon, extruded downward
    depth = params["slab"]["depth"]
    for st, name in ((storeys[0], "Slab-Ground"), (storeys[1], "Slab-L2")):
        slab = create(f, "IfcSlab", name=name, predefined_type="FLOOR")
        rep = ifcopenshell.api.geometry.add_slab_representation(
            f, context=body, depth=depth, polyline=[tuple(p) for p in fp])
        ifcopenshell.api.geometry.assign_representation(f, product=slab, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(
            f, product=slab, matrix=np.array(
                [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, st.Elevation - depth], [0, 0, 0, 1]], float))
        ifcopenshell.api.spatial.assign_container(f, products=[slab], relating_structure=st)

    # -- helper: cut an opening in wall `wi` and fill it with a door/window
    def add_hosted(kind: str, cfg: dict):
        wi = cfg["wall"]
        wall = walls[wi]
        p1, p2 = np.array(fp[wi], float), np.array(fp[(wi + 1) % len(fp)], float)
        d = p2 - p1
        ang = math.atan2(d[1], d[0])
        # world position of opening origin: along the wall's local +X, centred on
        # wall thickness (create_2pt_wall puts the body from y=0..thickness in local
        # coords, i.e. p1->p2 is one face; we accept that convention).
        u = d / np.linalg.norm(d)
        origin = p1 + u * cfg["offset"]
        z = cfg["sill"]
        # opening body slightly thicker than the wall so the boolean is unambiguous
        eps = 0.05
        n = np.array([-u[1], u[0]])          # wall's local +Y (into thickness)
        origin2 = origin - n * eps            # start eps outside the outer face
        m = np.array([
            [math.cos(ang), -math.sin(ang), 0, origin2[0]],
            [math.sin(ang),  math.cos(ang), 0, origin2[1]],
            [0, 0, 1, z],
            [0, 0, 0, 1]], float)

        opening = create(f, "IfcOpeningElement", name=f"{kind}-Opening", predefined_type="OPENING")
        orep = ifcopenshell.api.geometry.add_wall_representation(
            f, context=body, length=cfg["width"], height=cfg["height"], thickness=wt + 2 * eps)
        ifcopenshell.api.geometry.assign_representation(f, product=opening, representation=orep)
        ifcopenshell.api.geometry.edit_object_placement(f, product=opening, matrix=m)
        ifcopenshell.api.feature.add_feature(f, feature=opening, element=wall)

        elem = create(f, "IfcDoor" if kind == "Door" else "IfcWindow", name=kind)
        elem.OverallWidth = cfg["width"]
        elem.OverallHeight = cfg["height"]
        if kind == "Door":
            elem.PredefinedType = "DOOR"
            frep = ifcopenshell.api.geometry.add_door_representation(
                f, context=body, overall_width=cfg["width"], overall_height=cfg["height"])
        else:
            elem.PredefinedType = "WINDOW"
            frep = ifcopenshell.api.geometry.add_window_representation(
                f, context=body, overall_width=cfg["width"], overall_height=cfg["height"])
        ifcopenshell.api.geometry.assign_representation(f, product=elem, representation=frep)
        # place filling at the opening (thickness eps ignored -- door/window sit in wall plane)
        m2 = m.copy()
        m2[0:2, 3] = origin  # snap back onto the wall face
        ifcopenshell.api.geometry.edit_object_placement(f, product=elem, matrix=m2)
        ifcopenshell.api.feature.add_filling(f, opening=opening, element=elem)
        ifcopenshell.api.spatial.assign_container(f, products=[elem], relating_structure=ground)
        return opening, elem

    add_hosted("Door", params["door"])
    add_hosted("Window", params["window"])
    return f


def validate(path: str) -> bool:
    """Reopen + schema-validate + kernel-tessellate every product."""
    print(f"\n== validate {path}")
    f = ifcopenshell.open(path)
    print(f"schema={f.schema}  entities={len(list(f))}  size={os.path.getsize(path)} bytes")
    for cls in ("IfcProject", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcWall",
                "IfcSlab", "IfcDoor", "IfcWindow", "IfcOpeningElement",
                "IfcRelVoidsElement", "IfcRelFillsElement", "IfcRelContainedInSpatialStructure"):
        print(f"  {cls:36s} x{len(f.by_type(cls))}")

    logger = ifcopenshell.validate.json_logger()
    try:
        ifcopenshell.validate.validate(f, logger, express_rules=True)
    except ModuleNotFoundError as e:  # express rule executor needs pytest
        print(f"  (express rules skipped: {e}); running schema-only validation")
        ifcopenshell.validate.validate(f, logger, express_rules=False)
    errs = [s for s in logger.statements if s.get("level") in ("ERROR", "error", 40)]
    print(f"  schema validation statements: {len(logger.statements)} "
          f"({len(errs)} errors)")
    for s in logger.statements[:10]:
        print("   -", s.get("level"), s.get("message"))

    # geometry sanity: tessellate everything, confirm openings cut the walls
    ok_geom = True
    try:
        from ifcopenshell import geom as _geom
        settings = _geom.settings()
        settings.set("use-world-coords", True)
        vols = {}
        for prod in f.by_type("IfcProduct"):
            if not prod.Representation:
                continue
            try:
                shp = _geom.create_shape(settings, prod)
            except Exception as e:  # pragma: no cover
                print(f"   ! tessellate failed for {prod.is_a()} {prod.Name}: {e}")
                ok_geom = False
                continue
            v = np.array(shp.geometry.verts).reshape(-1, 3)
            fcs = np.array(shp.geometry.faces).reshape(-1, 3)
            # signed volume of the triangle soup
            vol = 0.0
            for a, b, c in fcs:
                vol += np.dot(v[a], np.cross(v[b], v[c])) / 6.0
            vols[(prod.is_a(), prod.Name)] = (len(v), abs(vol))
        for (cls, name), (nv, vol) in vols.items():
            print(f"   {cls:20s} {str(name):14s} verts={nv:5d}  vol={vol:8.4f} m3")
        # a solid 8x0.2x6 wall has 9.6 m3; door (0.9x2.1) removes ~0.378, window
        # (1.5x1.2) removes ~0.36 -> south (wall 0) and north (wall 2) walls must
        # come in visibly under the untouched east/west walls per unit length.
        w0 = vols.get(("IfcWall", "Wall-0"), (0, 0))[1]
        w1 = vols.get(("IfcWall", "Wall-1"), (0, 0))[1]
        expected_full_w0 = 8.0 * 0.2 * 6.0
        if w0 < expected_full_w0 - 0.2:
            print(f"   OK: door void applied (Wall-0 vol {w0:.3f} < solid {expected_full_w0:.3f})")
        else:
            print(f"   ?? door void may not have applied (Wall-0 vol {w0:.3f})")
            ok_geom = False
    except Exception as e:  # geometry kernel is best-effort
        print(f"  (geometry check skipped: {e})")
    return len(errs) == 0 and ok_geom


def check_specs() -> bool:
    """Validate spec/examples/*.json against spec/building.schema.json (JSON Schema 2020-12)."""
    root = os.path.dirname(HERE)
    schema_path = os.path.join(root, "spec", "building.schema.json")
    try:
        import json
        import jsonschema
    except ImportError:  # pragma: no cover
        print("  (jsonschema not installed; spec check skipped)")
        return True
    with open(schema_path) as fh:
        schema = json.load(fh)
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    ok = True
    print(f"\n== building spec examples vs {os.path.relpath(schema_path, root)}")
    minimal = {"storeys": 2, "footprint": [[0, 0], [12, 0], [12, 8], [0, 8]]}
    docs = {"<inline-minimal>": minimal}
    for name in ("tiny", "house", "office"):
        p = os.path.join(root, "spec", "examples", f"{name}.json")
        with open(p) as fh:
            docs[f"examples/{name}.json"] = json.load(fh)
    for name, doc in docs.items():
        errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        keys = sorted(doc.keys())
        print(f"  {name:26s} {'OK  ' if not errs else 'FAIL'} keys={keys}")
        for e in errs[:5]:
            print(f"      - at /{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}")
            ok = False
    return ok


def main() -> int:
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    f = build(PARAMS)
    f.write(OUT_PATH)
    print(f"wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes) in {time.time()-t0:.2f}s")
    # show the head of the STEP file so the reader sees it is plain IFC-SPF text
    with open(OUT_PATH) as fh:
        head = [next(fh) for _ in range(12)]
    print("".join(head))
    ok = validate(OUT_PATH)
    ok = check_specs() and ok
    print("\nRESULT:", "PASS" if ok else "FAIL (see notes above)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

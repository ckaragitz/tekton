#!/usr/bin/env python3
"""ifc_to_spec.py — turn a Claude-Design / any IFC into a tekton spec.json.

Closes the loop  Claude Design -> IFC -> spec.json -> native .rvt  with no
hand-authoring in the middle:

    python tools/ifc_to_spec.py design-or-hardened.ifc -o derived-spec.json
    python tools/spec_to_rvt.py --spec derived-spec.json --out room.rvt

Extracts (metres, degrees; local model coords):
  * levels    <- IfcBuildingStorey (name, elevation)
  * walls     <- IfcWall / IfcWallStandardCase (axis from placement + length
                 along local X; height/thickness from geometry bbox)
  * equipment <- IfcElectricDistributionBoard -> panelboard,
                 IfcTransformer -> transformer, IfcSwitchingDevice/
                 IfcElectricGenerator etc. -> proxy; position/rotation from the
                 ObjectPlacement, elevation from z, dims from the body bbox,
                 psets carried over verbatim, typeName from the type object.
Best results on a HARDENED IFC (real insertion points recovered) — see
skills/tekton-ifc/scripts/harden_ifc.py.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as uel
import ifcopenshell.util.placement as upl
import numpy as np

KIND_BY_CLASS = {
    "IfcElectricDistributionBoard": "panelboard",
    "IfcTransformer": "transformer",
    "IfcElectricFlowStorageDevice": "proxy",
    "IfcSwitchingDevice": "switchboard",
    "IfcDiscreteAccessory": "proxy",
    "IfcBuildingElementProxy": "proxy",
}


def _len_scale(f) -> float:
    """Metres per model length unit."""
    try:
        import ifcopenshell.util.unit as uu
        return uu.calculate_unit_scale(f)
    except Exception:
        return 1.0


def _placement_matrix(prod) -> np.ndarray:
    try:
        return np.array(upl.get_local_placement(prod.ObjectPlacement))
    except Exception:
        return np.eye(4)


def _bbox(f, prod, settings, scale):
    """World-space bbox of a product's body (metres) or None."""
    try:
        shape = ifcopenshell.geom.create_shape(settings, prod)
        v = np.array(shape.geometry.verts).reshape(-1, 3) * scale
        return v.min(axis=0), v.max(axis=0)
    except Exception:
        return None


def extract(path: str) -> dict:
    f = ifcopenshell.open(path)
    scale = _len_scale(f)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    proj = (f.by_type("IfcProject") or [None])[0]
    spec = {
        "specVersion": "1.0",
        "project": {"name": (proj.Name if proj else "Imported model") or "Imported model",
                    "description": f"Derived from {path} by ifc_to_spec.py"},
        "units": {"length": "m", "angle": "deg"},
        "levels": [], "walls": [], "equipment": [],
    }

    # ---- levels
    storeys = sorted(f.by_type("IfcBuildingStorey"), key=lambda s: (s.Elevation or 0.0))
    for i, st in enumerate(storeys):
        spec["levels"].append({"id": f"L{i + 1}", "name": st.Name or f"Level {i + 1}",
                               "elevation": round(float(st.Elevation or 0.0) * scale, 4)})
    if not spec["levels"]:
        spec["levels"].append({"id": "L1", "name": "Level 1", "elevation": 0.0})

    # ---- walls
    for w in list(f.by_type("IfcWall")):
        m = _placement_matrix(w)
        origin = m[:3, 3] * scale
        xdir = m[:3, 0]
        bb = _bbox(f, w, settings, scale)
        if bb is None:
            continue
        lo, hi = bb
        ext = hi - lo
        # wall runs along its local X; length = projection extent
        length = max(float(abs(np.dot(ext, xdir))), 0.05)
        thickness = float(min(ext[0], ext[1])) or 0.2
        height = float(ext[2]) or 3.0
        p0 = origin[:2]
        p1 = p0 + xdir[:2] / (np.linalg.norm(xdir[:2]) or 1.0) * length
        wtype = uel.get_type(w)
        spec["walls"].append({
            "id": w.Name or w.GlobalId,
            "start": [round(float(p0[0]), 4), round(float(p0[1]), 4)],
            "end": [round(float(p1[0]), 4), round(float(p1[1]), 4)],
            "thickness": round(thickness, 4), "height": round(height, 4),
            "type": (wtype.Name if wtype else None) or "Generic wall",
        })

    # ---- room shell fallback: some Design exports model the room as ONE
    # IfcBuildingElementProxy / IfcSpace instead of IfcWall entities. If we
    # found no walls, synthesize the four perimeter walls from the largest
    # tall, thin-walled proxy/space footprint.
    if not spec["walls"]:
        best = None
        for cls in ("IfcBuildingElementProxy", "IfcSpace"):
            for pr in f.by_type(cls):
                bb = _bbox(f, pr, settings, scale)
                if bb is None:
                    continue
                lo, hi = bb
                ext = hi - lo
                # room-like: sizeable footprint and taller than a metre
                if ext[0] > 1.5 and ext[1] > 1.5 and ext[2] > 1.0:
                    area = ext[0] * ext[1]
                    if best is None or area > best[0]:
                        best = (area, lo, hi, pr)
        if best:
            _, lo, hi, pr = best
            h = round(float((hi - lo)[2]), 4)
            t = 0.2
            x0, y0, x1, y1 = float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])
            ring = [((x0, y0), (x1, y0), "S"), ((x1, y0), (x1, y1), "E"),
                    ((x1, y1), (x0, y1), "N"), ((x0, y1), (x0, y0), "W")]
            for (a, b, tag) in ring:
                spec["walls"].append({
                    "id": f"W-{tag}", "start": [round(a[0], 4), round(a[1], 4)],
                    "end": [round(b[0], 4), round(b[1], 4)],
                    "thickness": t, "height": h,
                    "type": "Room shell (derived from proxy footprint)",
                    "derivedFrom": pr.Name or pr.GlobalId,
                })
            spec.setdefault("notes", []).append(
                f"walls synthesized from the footprint of {pr.is_a()} "
                f"'{pr.Name}' ({round(x1-x0,2)} x {round(y1-y0,2)} m, h={h} m)")

    # ---- equipment
    for cls, kind in KIND_BY_CLASS.items():
        for eq in list(f.by_type(cls)):
            m = _placement_matrix(eq)
            pos = m[:3, 3] * scale
            xdir = m[:3, 0]
            rot = math.degrees(math.atan2(float(xdir[1]), float(xdir[0])))
            bb = _bbox(f, eq, settings, scale)
            dims = None
            if bb is not None:
                lo, hi = bb
                ext = (hi - lo)
                dims = {"w": round(float(ext[0]), 4), "d": round(float(ext[1]), 4),
                        "h": round(float(ext[2]), 4)}
            psets = {}
            try:
                for pname, props in (uel.get_psets(eq) or {}).items():
                    clean = {k: v for k, v in props.items() if k != "id"}
                    if clean:
                        psets[pname] = clean
            except Exception:
                pass
            etype = uel.get_type(eq)
            rec = {
                "kind": kind, "name": eq.Name or eq.GlobalId,
                "level": "L1",
                "position": [round(float(pos[0]), 4), round(float(pos[1]), 4)],
                "rotationDeg": round(rot, 2),
                "elevation": round(float(pos[2]), 4),
                "typeName": (etype.Name if etype else None) or (eq.ObjectType or kind),
                "description": eq.Description,
                "tag": eq.Tag or eq.Name,
                "ifcClass": cls,
            }
            if dims:
                rec["dims"] = dims
            if psets:
                rec["psets"] = psets
            spec["equipment"].append(rec)
    return spec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IFC -> tekton spec.json")
    ap.add_argument("ifc")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    spec = extract(a.ifc)
    with open(a.out, "w") as fh:
        json.dump(spec, fh, indent=2)
    print(f"derived spec: {len(spec['levels'])} level(s), {len(spec['walls'])} wall(s), "
          f"{len(spec['equipment'])} equipment item(s) -> {a.out}")
    kinds = {}
    for e in spec["equipment"]:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"  equipment by kind: {kinds}")
    for e in spec["equipment"][:12]:
        print(f"    {e['kind']:11s} {e['name']:12s} at {e['position']} el={e['elevation']} "
              f"type={e['typeName'][:38]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

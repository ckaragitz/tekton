"""oracle_ifc.py -- summarise a Revit-exported IFC as ground truth.

    .venv/bin/python tests/oracle/oracle_ifc.py <file.ifc> [--refresh]

Uses ifcopenshell. Extracts (and caches under tests/oracle/cache/):

  * header      schema (IFC2X3/IFC4), authoring application, VersionGUID /
                NumberOfSaves from the FILE_DESCRIPTION (Revit stamps these;
                the VersionGUID matches an episode GUID in Global/History)
  * counts      entity counts per IfcProduct subtype, per IfcTypeObject
  * storeys     name + elevation (+ Revit ElementId from Tag)
  * elements    per product: is_a, Name, ObjectType, Tag (= Revit ElementId
                for Revit exports), storey name, type name  -> the per-
                element ground truth compare_oracle joins on
  * types       IfcTypeObject names (Revit "Family:Type"), materials, spaces
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def cache_path(path: str) -> str:
    st = os.stat(path)
    h = hashlib.sha256(f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{os.path.basename(path)}.{h[:10]}.ifc.json")


def _int_tag(t):
    try:
        return int(str(t).strip())
    except Exception:  # noqa: BLE001
        return None


def _split_revit_name(name: str):
    """Revit exports Name as 'Family:Type:ElementId' (elements) or
    'Family:Type' (types). Return (family, type, id_or_None)."""
    if not name:
        return None, None, None
    parts = name.split(":")
    if len(parts) >= 3 and _int_tag(parts[-1]) is not None:
        return ":".join(parts[:-2]) if len(parts) > 3 else parts[0], parts[-2], _int_tag(parts[-1])
    if len(parts) == 2:
        return parts[0], parts[1], None
    return name, None, None


def extract(path: str, refresh: bool = False, quiet: bool = False) -> dict:
    cp = cache_path(path)
    if not refresh and os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    t0 = time.time()
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, file=sys.stderr))
    import ifcopenshell
    import ifcopenshell.util.element as U

    f = ifcopenshell.open(path)
    out: dict = {"file": os.path.abspath(path), "basename": os.path.basename(path),
                 "schema": f.schema}

    # header (parse the STEP header text for Revit's stamps)
    with open(path, "rb") as fh:
        head = fh.read(4000).decode("latin-1", "replace")
    m = re.search(r"VersionGUID:\s*([0-9a-fA-F-]{36})", head)
    n = re.search(r"NumberOfSaves:\s*(\d+)", head)
    app = re.search(r"'(Autodesk Revit[^']*)'", head)
    out["header"] = {
        "version_guid": m.group(1).lower() if m else None,
        "number_of_saves": int(n.group(1)) if n else None,
        "application": app.group(1) if app else None,
    }
    proj = f.by_type("IfcProject")
    out["project_name"] = proj[0].Name if proj else None
    site = f.by_type("IfcSite")
    out["site_name"] = site[0].Name if site else None

    # entity counts
    prod_counts = collections.Counter(e.is_a() for e in f.by_type("IfcProduct"))
    type_counts = collections.Counter(e.is_a() for e in f.by_type("IfcTypeObject"))
    out["product_counts"] = dict(prod_counts.most_common())
    out["type_counts"] = dict(type_counts.most_common())
    out["n_entities"] = len(list(f))
    log(f"[ifc] {os.path.basename(path)} {f.schema} products={sum(prod_counts.values())} "
        f"entities={out['n_entities']}")

    # storeys
    storeys = []
    for s in f.by_type("IfcBuildingStorey"):
        storeys.append({"name": s.Name, "elevation": float(s.Elevation or 0.0),
                        "tag": _int_tag(getattr(s, "Tag", None)),
                        "guid": s.GlobalId})
    storeys.sort(key=lambda x: x["elevation"])
    out["storeys"] = storeys

    # storey membership map (element -> storey name)
    elem_storey = {}
    for rel in f.by_type("IfcRelContainedInSpatialStructure"):
        st = rel.RelatingStructure
        if st.is_a("IfcBuildingStorey"):
            for e in rel.RelatedElements:
                elem_storey[e.id()] = st.Name

    # type map (element -> type name)
    elem_type = {}
    for rel in f.by_type("IfcRelDefinesByType"):
        t = rel.RelatingType
        for e in rel.RelatedObjects:
            elem_type[e.id()] = t.Name

    # elements
    elements = []
    for e in f.by_type("IfcProduct"):
        if e.is_a() in ("IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpatialZone"):
            continue
        tag = _int_tag(getattr(e, "Tag", None))
        fam, typ, name_id = _split_revit_name(e.Name)
        elements.append({
            "step_id": e.id(), "is_a": e.is_a(), "name": e.Name,
            "family": fam, "type_name": typ,
            "tag": tag if tag is not None else name_id,
            "object_type": getattr(e, "ObjectType", None),
            "storey": elem_storey.get(e.id()),
            "type_object": elem_type.get(e.id()),
            "predefined": str(getattr(e, "PredefinedType", None) or ""),
        })
    out["elements"] = elements
    out["n_elements_with_tag"] = sum(1 for e in elements if e["tag"] is not None)

    # types
    types = []
    for t in f.by_type("IfcTypeObject"):
        fam, typ, _ = _split_revit_name(t.Name)
        types.append({"is_a": t.is_a(), "name": t.Name, "family": fam,
                      "type_name": typ, "tag": _int_tag(getattr(t, "Tag", None))})
    out["types"] = types

    # spaces
    out["spaces"] = [{"name": sp.Name, "long_name": sp.LongName,
                      "storey": elem_storey.get(sp.id()),
                      "tag": _int_tag(getattr(sp, "Tag", None))}
                     for sp in f.by_type("IfcSpace")]

    # materials
    out["materials"] = sorted({mat.Name for mat in f.by_type("IfcMaterial") if mat.Name})

    out["timing_s"] = round(time.time() - t0, 2)
    with open(cp, "w") as fh:
        json.dump(out, fh)
    log(f"[ifc] cached -> {cp} ({out['timing_s']}s)")
    return out


def print_summary(s: dict) -> None:
    h = s["header"]
    print(f"== {s['basename']}  {s['schema']}  by {h.get('application')}")
    print(f"   VersionGUID {h.get('version_guid')}  saves={h.get('number_of_saves')}  "
          f"project={s.get('project_name')!r} site={s.get('site_name')!r}")
    print(f"   entities={s['n_entities']:,}  elements={len(s['elements']):,}  "
          f"with Revit ElementId tag={s['n_elements_with_tag']:,}")
    print("   product counts:")
    for k, v in list(s["product_counts"].items())[:20]:
        print(f"     {v:6d}  {k}")
    print("   type counts:", ", ".join(f"{k}={v}" for k, v in s["type_counts"].items()))
    print(f"   storeys ({len(s['storeys'])}):")
    for st in s["storeys"]:
        print(f"     {st['elevation']:9.3f}  {st['name']!r}  tag={st['tag']}")
    if s["materials"]:
        print(f"   materials ({len(s['materials'])}): " + ", ".join(s["materials"][:10]))
    tnames = sorted({t['name'] for t in s['types'] if t['name']})[:12]
    print(f"   type names sample: {tnames}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ifc", nargs="?", default=os.path.join(
        os.path.dirname(os.path.dirname(HERE)),
        "vendor/magnetar-revit-test-datasets/IFC Exports/2024_Core_Interior_slim.ifc"))
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    print_summary(extract(args.ifc, refresh=args.refresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())

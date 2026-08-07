#!/usr/bin/env python3
"""make_hosting.py — build the WALL-HOSTING acceptance files.

Produces (from the Revit MEP sample as template):

  H1_panel_on_existing_wall.rvt
      a NEW 480 V panelboard (symbol 619617) MOUNTED on the face of the
      EXISTING electrical-room wall 573608 via a new GeomOnPlaneRef
      SketchPlane (geomTag 6 = the face that looks into room 573809 —
      the same face Autodesk's own panels 581482-581485 are flush with,
      though those hang off a reference-less DummyPlaneRef plane).
      Proves: SketchPlane authoring + real face reference into a wall +
      instance hosted on it (m_hostId, m_workPlaneBased).

  H2_panel_on_created_wall.rvt
      a NEW interior partition (type 563416) created inside the electrical
      room AND a new panel hosted on ITS room-side face (geomTag 5) —
      the "electrical room built from scratch" case.  The face reference
      points at a wall whose solid Revit must regenerate first.

  H3_panel_on_created_wall_dummyplane.rvt
      identical to H2 but the SketchPlane is a DummyPlaneRef work plane
      COINCIDENT with the new wall's face (no reference into the wall).
      The guaranteed-safe fallback: if H2's face-ref does not survive the
      translator, H3 isolates the cause.

Run from the repo root:
    .venv/bin/python experiments/hosting/make_hosting.py
Each file is committed with rvt.commit.commit_new_elements and proven with
rvt.commit.verify_written; results go to experiments/hosting/manifest.json.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import commit_new_elements, verify_written  # noqa: E402
from rvt.mutate import Document  # noqa: E402
from rvt import hosting  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
TEMPLATE = "rmebasicsampleproject"

# template constants (rme)
LEVEL1 = 378117                    # 'Level 1', elevation 0.309 ft
WALL_TYPE = 563416                 # most-used basic wall (0.377 ft thick)
PANEL_480V = 619617                # 480V MCB Surface :: 400 A (panelboard symbol)
EXISTING_WALL = 573608             # electrical-room wall, face x=59.256, y 104.8..125.7
ROOM_INSIDE_POINT = (60.5, 115.0)  # a point INSIDE room 573809 (x 59.26..68.92)


def _plan_H1():
    doc = Document.load(TEMPLATE)
    # the face of wall 573608 that looks into the electrical room:
    tag = hosting.side_facing_point(doc, EXISTING_WALL, ROOM_INSIDE_POINT)
    sp, panel = hosting.host_instance_on_wall(
        doc, symbol_id=PANEL_480V, wall=EXISTING_WALL,
        distance_along_ft=6.0,          # 6 ft from the wall start (clear of panels 581482-85)
        elevation_ft=4.0,               # mounting height above Level 1
        side=tag, level_id=LEVEL1)
    return doc, [sp, panel], {
        "case": "H1", "wall": EXISTING_WALL, "wall_state": "EXISTING",
        "face_tag": tag, "plane_ref": "geom",
        "proves": ("new SketchPlane with a real GeomOnPlaneRef face reference "
                   "(m_elemId=wall, m_geomTag) + a new 480 V panelboard hosted "
                   "on it (m_hostId = the SketchPlane, m_workPlaneBased). "
                   "The panel arrives MOUNTED on wall 573608's room-side face."),
    }


def _plan_created_wall(plane_ref: str, case: str):
    doc = Document.load(TEMPLATE)
    # a NEW partition inside the electrical room (room x 59.26..68.92,
    # y 105.09..125.48): x = 64.5, running y 118 -> 106 (12 ft), 8 ft high.
    wall = doc.add_wall(level_id=LEVEL1, wall_type_id=WALL_TYPE,
                        p0=(64.5, 118.0), p1=(64.5, 106.0), height=8.0)
    # host the panel on the side that faces the existing panels (x < 64.5):
    tag = hosting.side_facing_point(doc, wall, ROOM_INSIDE_POINT)
    sp, panel = hosting.host_instance_on_wall(
        doc, symbol_id=PANEL_480V, wall=wall,
        distance_along_ft=6.0, elevation_ft=4.0,
        side=tag, level_id=LEVEL1, plane_ref=plane_ref)
    return doc, [wall, sp, panel], {
        "case": case, "wall": wall.elem_id, "wall_state": "CREATED (same run)",
        "face_tag": tag, "plane_ref": plane_ref,
        "proves": (("new wall + SketchPlane with GeomOnPlaneRef -> the NEW wall "
                    "(face resolves at regeneration) + hosted 480 V panel: the "
                    "electrical-room-from-scratch case.")
                   if plane_ref == "geom" else
                   ("new wall + DummyPlaneRef work plane coincident with its face "
                    "(no reference into the wall) + hosted panel: the guaranteed "
                    "regeneration-independent fallback for H2.")),
    }


def _readback(path: str, ids: dict) -> dict:
    """Decode the written file and prove the hosting fields landed."""
    d = Document.from_file(path)
    out = {}
    sp = d.value(ids["sketchplane"]) or {}
    pref = sp.get("m_oPlaneRef") or {}
    out["sketchplane"] = {
        "id": ids["sketchplane"], "class": d.class_of(ids["sketchplane"]),
        "planeref_class": pref.get("ptr_class"),
        "geomRef": ((pref.get("value") or {}).get("m_geomRef")
                    if pref.get("ptr_class") == "GeomOnPlaneRef" else None),
        "trf": ((sp.get("m_oTrf") or {}).get("value") or {}),
    }
    inst = d.value(ids["panel"]) or {}
    ii = ((inst.get("m_pInstanceInfo") or {}).get("value")) or {}
    out["panel"] = {
        "id": ids["panel"], "class": d.class_of(ids["panel"]),
        "m_hostId": inst.get("m_hostId"),
        "m_workPlaneBased": inst.get("m_workPlaneBased"),
        "m_scheduleOnlyLevelId": inst.get("m_scheduleOnlyLevelId"),
        "symbol": ii.get("m_symbolId"), "master": inst.get("m_masterSymbolId"),
        "trf": ii.get("m_Trf"),
        "hosted_on_our_sketchplane": inst.get("m_hostId") == ids["sketchplane"],
    }
    if "wall" in ids:
        out["wall"] = {"id": ids["wall"], "class": d.class_of(ids["wall"]),
                       "exists": d.exists(ids["wall"])}
        gr = out["sketchplane"]["geomRef"] or {}
        out["sketchplane"]["references_wall"] = (gr.get("m_elemId") == ids["wall"]) if gr else None
    return out


def _build(plan_fn, out_name: str, manifest: dict, *args):
    doc, elements, info = plan_fn(*args)
    # referential integrity BEFORE writing
    dangling = {e.elem_id: doc.check_references(e) for e in elements}
    records = [dict(doc.serialize(e)) for e in elements]
    plans = [e.elemrec for e in elements]
    out_path = os.path.join(HERE, out_name)
    rep = commit_new_elements(SRC, out_path, records, plans)
    ids = [e.elem_id for e in elements]
    v = verify_written(out_path, ids)
    clean = {s: sum(1 for x in v["new_ids_found"][s].values() if x["clean"])
             for s in (101, 102, 103)}
    structural_ok = (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
                     and v["walker_errors"] == 0 and v["stamps_ok"]
                     and all(n == len(ids) for n in clean.values())
                     and v["elemtable_count"] == v["header_count"]
                     and all(v["sentinel_last"].values()))
    role = {}
    for e in elements:
        role[e.kind if e.kind != "hosted_instance" else "panel"] = e.elem_id
    if "wall" in role:
        pass
    rb = _readback(out_path, role)
    hosting_ok = (rb["panel"]["hosted_on_our_sketchplane"]
                  and rb["panel"]["m_workPlaneBased"] is True
                  and rb["sketchplane"]["class"] == "SketchPlane")
    if info["plane_ref"] == "geom":
        gr = rb["sketchplane"]["geomRef"] or {}
        hosting_ok = hosting_ok and gr.get("m_elemId") == info["wall"] \
            and gr.get("m_geomTag") == info["face_tag"]
    entry = {
        **info,
        "file": os.path.relpath(out_path, ROOT),
        "size_bytes": os.path.getsize(out_path),
        "elements": [{"id": e.elem_id, "kind": e.kind, "class": e.class_name,
                      "template": e.template_id, "notes": e.notes}
                     for e in elements],
        "dangling_refs_before_write": dangling,
        "elemtable": {"before": rep.elemtable_count_before,
                      "after": rep.elemtable_count_after},
        "verify_written": {"crc_failures": v["crc_failures"],
                           "ecc_mismatches": v["ecc_mismatches"],
                           "walker_errors": v["walker_errors"],
                           "stamps_ok": v["stamps_ok"],
                           "new_records_clean_per_seq": clean,
                           "counts_match": v["elemtable_count"] == v["header_count"],
                           "sentinels_last": all(v["sentinel_last"].values())},
        "readback": rb,
        "STRUCTURALLY_VALID": bool(structural_ok),
        "HOSTING_VERIFIED": bool(hosting_ok),
    }
    manifest["files"].append(entry)
    tag = info["face_tag"]
    print(f"\n=== {info['case']}  {out_name}")
    print(f"  wall {info['wall']} ({info['wall_state']}), face tag {tag} "
          f"({'exterior/left' if tag == 6 else 'interior/right'} side), plane_ref={info['plane_ref']}")
    for e in elements:
        print(f"  + {e.class_name:14s} id {e.elem_id}  ({e.kind})")
    print(f"  ElemTable {rep.elemtable_count_before} -> {rep.elemtable_count_after}; "
          f"CRC {v['crc_failures']} ECC {v['ecc_mismatches']} walker {v['walker_errors']} "
          f"stamps {v['stamps_ok']} clean/seq {clean}")
    print(f"  readback: panel.m_hostId={rb['panel']['m_hostId']} "
          f"workPlaneBased={rb['panel']['m_workPlaneBased']} "
          f"scheduleOnlyLevel={rb['panel']['m_scheduleOnlyLevelId']} "
          f"planeref={rb['sketchplane']['planeref_class']} "
          f"geomRef={ (rb['sketchplane']['geomRef'] or {}).get('m_elemId') },"
          f"tag { (rb['sketchplane']['geomRef'] or {}).get('m_geomTag') }")
    print(f"  STRUCTURALLY VALID: {structural_ok}   HOSTING VERIFIED: {hosting_ok}")
    return structural_ok and hosting_ok


def main() -> int:
    manifest = {"template": SRC, "symbol": PANEL_480V, "files": []}
    ok = True
    ok &= _build(_plan_H1, "H1_panel_on_existing_wall.rvt", manifest)
    ok &= _build(_plan_created_wall, "H2_panel_on_created_wall.rvt", manifest, "geom", "H2")
    ok &= _build(_plan_created_wall, "H3_panel_on_created_wall_dummyplane.rvt",
                 manifest, "dummy", "H3")
    manifest["all_ok"] = bool(ok)
    with open(os.path.join(HERE, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, default=str)
    print("\nwrote", os.path.join(HERE, "manifest.json"))
    print("ALL OK" if ok else "SOME CHECK FAILED — see manifest.json")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

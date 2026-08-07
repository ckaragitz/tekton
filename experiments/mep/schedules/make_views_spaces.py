#!/usr/bin/env python3
"""make_views_spaces.py — proof files for PANEL SCHEDULE VIEWS and MEP
SPACES / SPACE TAGS (stream: mep views+spaces; module rvt.mep.views_spaces).

Every cell of the CRUD matrix below is written by the real writer, proven
structurally (rvt.commit.verify_written / rvt.manipulate.verify_manipulated),
re-read semantically, and gated by tools/rvt_validate.py (must be 0 errors).
Autodesk-viewer certification is the orchestrator's job.

  experiments/mep/schedules/
    panel_schedule_view.rvt         CREATE: a NEW panelboard (+ transformer +
                                    receptacle loads + 2 circuits, all created
                                    in the same commit) AND its PanelScheduleView
                                    8-element cluster, rewired to the new panel
                                    (m_targetId), m_outOfDate=True (Revit
                                    regenerates the table from the panel's
                                    circuits on open).
    panel_schedule_view_current.rvt CREATE control: identical but m_outOfDate=
                                    False and the cloned slot cache kept —
                                    isolates the freshness flag if the viewer
                                    rejects one variant.
    panel_schedule_view_rename.rvt  MODIFY: existing schedule view 709455
                                    'LP-1' renamed (DBView.m_viewName).
    panel_schedule_view_delete.rvt  DELETE: existing schedule view 709461
                                    'EP-3' + its owned cluster (cascade).
  experiments/mep/spaces/
    space_create.rvt                CREATE: 4 new walls closing an electrical
                                    room + a new HVAC ZoneElement + a new
                                    Space (RoomElem, OST_MEPSpaces) placed at
                                    a point inside them + its Space Tag in the
                                    Level-1 HVAC plan.
    space_rename.rvt                MODIFY: existing space 379575 renamed and
                                    renumbered (ROOM_NAME / ROOM_NUMBER params).
    space_delete.rvt                DELETE: existing space 379575 (cascade: its
                                    tag; zone/topology mentions neutralised).

Run from the repo root:  .venv/bin/python experiments/mep/schedules/make_views_spaces.py [names...]
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SPACES_DIR = os.path.join(ROOT, "experiments", "mep", "spaces")
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import verify_written  # noqa: E402
from rvt.mutate import Document  # noqa: E402
from rvt import manipulate  # noqa: E402
from rvt.mep import views_spaces as vs  # noqa: E402
from rvt.validate import validate_file  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

# ---- rme template constants ----------------------------------------------
LEVEL1 = 378117            # 'Level 1' (elev 0.309 ft)
WALL_TYPE = 563416         # basic wall type, 0.377 ft thick (most used)
PANEL_480V = 619617        # 480V MCB Surface :: 400 A panelboard
XFMR_500KVA = 621242       # Dry Type 480-208Y120 :: 500 kVA
RECEPTACLE = 342654        # duplex receptacle 'Standard'
SPACE_379575 = 379575      # space 'Technology' 28 (has tag 379576)
VIEW_LP1 = 709455          # PanelScheduleView 'LP-1' (panel 581482)
VIEW_EP3 = 709461          # PanelScheduleView 'EP-3' (panel 503251)

RESULTS: dict = {"template": SRC, "files": {}}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _validate(path: str) -> dict:
    rep = validate_file(path)
    errs = [f.to_json() for f in rep.errors]
    warns = [f.to_json() for f in rep.warnings]
    return {"ok": bool(rep.ok), "errors": errs[:10], "n_errors": len(errs),
            "warnings": warns[:6], "n_warnings": len(warns),
            "stats": {k: rep.stats.get(k) for k in
                      ("records", "elements_decoded", "decode_failures",
                       "refs_checked", "connector_edges") if k in rep.stats},
            "text": rep.format_text(max_findings=8)}


def _structural_ok_created(v: dict, ids: list) -> bool:
    clean = {s: sum(1 for x in v["new_ids_found"][s].values() if x["clean"])
             for s in (101, 102, 103)}
    return (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
            and v["walker_errors"] == 0 and v["stamps_ok"]
            and all(n == len(ids) for n in clean.values())
            and v["elemtable_count"] == v["header_count"]
            and all(v["sentinel_last"].values()))


def _structural_ok_manip(v: dict) -> bool:
    return (v.get("crc_failures") == 0 and v.get("ecc_mismatches") == 0
            and v.get("walker_errors") == 0
            and v.get("isize_identity_mismatches") == 0
            and bool(v.get("stamps_ok"))
            and all(v.get("sentinel_last", {}).values())
            and v.get("elemtable_count") == v.get("header_count")
            and not v.get("deleted_still_present")
            and not v.get("deleted_in_elemtable")
            and v.get("elemtable_ids_sorted") is not False
            and v.get("unit0_ids_equal_elemtable") is not False)


def _record(name: str, entry: dict) -> None:
    RESULTS["files"][name] = entry
    status = "VALIDATES" if entry.get("validate", {}).get("ok") and entry.get(
        "structural_ok", True) else "BLOCKED"
    entry["status"] = status
    print(f"[{name}] {status} — {entry.get('summary', '')}")


# ===========================================================================
# CREATE: panel + circuits + panel schedule view
# ===========================================================================
def make_panel_schedule_view(name: str, *, out_of_date: bool) -> None:
    out_path = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    lvl = LEVEL1
    # a new panelboard + its loads + circuits (the "our created circuits" case)
    panel = doc.add_family_instance(PANEL_480V, lvl, position=(50.0, -90.0, 3.5))
    xfmr = doc.add_family_instance(XFMR_500KVA, lvl, position=(50.0, -100.0, 0.3))
    rcpt = doc.add_family_instance(RECEPTACLE, lvl, position=(56.0, -100.0, 1.5))
    c1 = doc.add_circuit(panel, xfmr, number="1", description="XFMR T-NEW feeder",
                         rating=200.0, poles=3)
    c2 = doc.add_circuit(panel, rcpt, number="2", description="Receptacles",
                         rating=20.0, poles=1)
    # the deliverable: the panel's schedule view (name = the panel's name)
    cluster = vs.add_panel_schedule_view(doc, panel, name="EP-NEW-1",
                                         out_of_date=out_of_date)
    view = cluster[0]
    elements = [panel, xfmr, rcpt, c1, c2] + cluster
    rep = vs.commit_elements(SRC, out_path, doc, elements)
    ids = [e.elem_id for e in elements]
    v = verify_written(out_path, ids)
    sok = _structural_ok_created(v, ids)
    # semantic readback
    d = Document.from_file(out_path)
    desc = vs.describe_panel_schedule_view(d, view.elem_id)
    ph = d.value(panel.elem_id, 101) or {}
    regen = ((ph.get("m_parents") or {}).get("value") or {}).get("m_regenOnly") or []
    readback = {
        "view": desc,
        "target_is_new_panel": desc["target_panel"] == panel.elem_id,
        "template": desc["template"],
        "template_name": (d.value(desc["template"]) or {}).get("m_name"),
        "cluster_owners": {str(e): (d.et_by_id[e].owner_id if e in d.et_by_id else None)
                           for e, _ in desc["cluster"]},
        "panel_regenOnly_lists_view": view.elem_id in regen,
        "circuits": [c1.elem_id, c2.elem_id],
    }
    sem_ok = (readback["target_is_new_panel"]
              and len(desc["cluster"]) == len(cluster)
              and readback["panel_regenOnly_lists_view"]
              and desc["class"] == "PanelScheduleView")
    val = _validate(out_path)
    _record(name, {
        "verb": "create", "category": "PanelScheduleView",
        "out": os.path.relpath(out_path, ROOT),
        "elements": {"panel": panel.elem_id, "loads": [xfmr.elem_id, rcpt.elem_id],
                     "circuits": [c1.elem_id, c2.elem_id],
                     "schedule_view": view.elem_id,
                     "cluster": [(e.elem_id, e.class_name) for e in cluster]},
        "out_of_date": out_of_date,
        "commit": {"elemtable_before": rep.elemtable_count_before,
                   "elemtable_after": rep.elemtable_count_after,
                   "watermark_after": rep.watermark_after,
                   "bytes_added": rep.per_seq_bytes_added},
        "verify_written": v, "structural_ok": sok,
        "readback": readback, "semantic_ok": sem_ok,
        "validate": val,
        "summary": (f"new panel {panel.elem_id} + circuits {c1.elem_id},{c2.elem_id} "
                    f"+ PanelScheduleView {view.elem_id} (cluster of {len(cluster)}), "
                    f"outOfDate={out_of_date}; validator errors={val['n_errors']}"),
    })


# ===========================================================================
# MODIFY / DELETE an existing schedule view
# ===========================================================================
def make_schedule_view_rename(name: str) -> None:
    out_path = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    old = (doc.value(VIEW_LP1) or {}).get("m_viewName")
    new_name = f"{old}-RENAMED"
    plan = vs.rename_panel_schedule_view(doc, VIEW_LP1, new_name)
    rep = manipulate.commit_plans(SRC, out_path, [plan])
    v = manipulate.verify_manipulated(out_path, edited_ids=[VIEW_LP1])
    d = Document.from_file(out_path)
    got = (d.value(VIEW_LP1) or {}).get("m_viewName")
    val = _validate(out_path)
    _record(name, {
        "verb": "modify", "category": "PanelScheduleView",
        "out": os.path.relpath(out_path, ROOT),
        "edit": {"view": VIEW_LP1, "old_name": old, "new_name": new_name,
                 "readback_name": got},
        "commit": rep.to_json(), "verify_manipulated": v,
        "structural_ok": _structural_ok_manip(v),
        "semantic_ok": got == new_name,
        "validate": val,
        "summary": f"view {VIEW_LP1} {old!r} -> {got!r}; validator errors={val['n_errors']}",
    })


def make_schedule_view_delete(name: str) -> None:
    out_path = os.path.join(HERE, name)
    doc = Document.from_file(SRC)
    cluster = vs.owned_cluster(doc, VIEW_EP3)
    report = manipulate.dependency_report(doc, VIEW_EP3)
    plan = vs.delete_panel_schedule_view(doc, VIEW_EP3, cascade=True)
    deleted = list(plan.ids_to_remove)
    rep = manipulate.commit_plans(SRC, out_path, [plan])
    v = manipulate.verify_manipulated(out_path, deleted_ids=deleted,
                                       edited_ids=[e for e in plan.edited_ids
                                                   if e not in set(deleted)])
    d = Document.from_file(out_path)
    gone = [e for e in cluster if not d.exists(e)]
    still = [e for e in cluster if d.exists(e)]
    val = _validate(out_path)
    _record(name, {
        "verb": "delete", "category": "PanelScheduleView",
        "out": os.path.relpath(out_path, ROOT),
        "edit": {"view": VIEW_EP3, "owned_cluster": cluster,
                 "closure_deleted": deleted,
                 "referrers_neutralised": len(plan.referrer_edits)
                 if hasattr(plan, "referrer_edits") else len(plan.edited_ids),
                 "dependency_report": {k: report.get(k) for k in
                                       ("hard_dependents", "referrers", "closure")
                                       if k in report}},
        "commit": rep.to_json(), "verify_manipulated": v,
        "structural_ok": _structural_ok_manip(v),
        "semantic_ok": (not still) and set(cluster) <= set(deleted),
        "readback": {"cluster_gone": gone, "cluster_still_present": still},
        "validate": val,
        "summary": (f"view {VIEW_EP3} + owned cluster {len(cluster)} deleted "
                    f"({len(deleted)} elements in closure); validator errors="
                    f"{val['n_errors']}"),
    })


# ===========================================================================
# CREATE: electrical room walls + zone + space + space tag
# ===========================================================================
def make_space_create(name: str) -> None:
    out_path = os.path.join(SPACES_DIR, name)
    doc = Document.from_file(SRC)
    lvl = LEVEL1
    # a NEW closed electrical room, clear of the model: 20 x 16 ft
    x0, y0, x1, y1 = 100.0, -120.0, 120.0, -104.0
    walls = [
        doc.add_wall(lvl, WALL_TYPE, (x0, y0), (x1, y0), height=10.0),   # south
        doc.add_wall(lvl, WALL_TYPE, (x1, y0), (x1, y1), height=10.0),   # east
        doc.add_wall(lvl, WALL_TYPE, (x1, y1), (x0, y1), height=10.0),   # north
        doc.add_wall(lvl, WALL_TYPE, (x0, y1), (x0, y0), height=10.0),   # west
    ]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    zone = vs.add_zone(doc, name="ELEC")
    space = vs.add_space(doc, lvl, (cx, cy), name="ELECTRICAL ROOM", number="E101",
                         upper_offset=10.0, bounding_walls=walls, zone=zone)
    tag = vs.add_space_tag(doc, space)
    elements = walls + [zone, space, tag]
    rep = vs.commit_elements(SRC, out_path, doc, elements)
    ids = [e.elem_id for e in elements]
    v = verify_written(out_path, ids)
    sok = _structural_ok_created(v, ids)
    d = Document.from_file(out_path)
    ds = vs.describe_space(d, space.elem_id)
    tv = d.value(tag.elem_id) or {}
    tagged = (tv.get("m_taggedRoomElemId") or {}).get("m_linkInstOrHostId")
    zv = d.value(zone.elem_id) or {}
    readback = {
        "space": ds,
        "space_class": d.class_of(space.elem_id),
        "space_category": d.category_of(space.elem_id),
        "tag": {"id": tag.elem_id, "class": d.class_of(tag.elem_id),
                "category": d.category_of(tag.elem_id),
                "tags_space": tagged, "owner_view": tv.get("m_ownerDBViewId"),
                "symbol": tv.get("m_symbolId"),
                "head": ((tv.get("m_oTagOrientationCell") or {}).get("value") or {}).get("m_headLocation")},
        "zone": {"id": zone.elem_id, "class": d.class_of(zone.elem_id),
                 "space_ids": zv.get("m_spaceIds")},
        "walls_exist": all(d.exists(w.elem_id) for w in walls),
    }
    sem_ok = (ds["name"] == "ELECTRICAL ROOM" and ds["number"] == "E101"
              and ds["point"] == [cx, cy] and ds["level"] == lvl
              and set(ds["bounding"]) == {w.elem_id for w in walls}
              and ds["zone"] == zone.elem_id
              and zv.get("m_spaceIds") == [space.elem_id]
              and tagged == space.elem_id
              and readback["space_category"] == vs.OST_MEPSpaces
              and readback["tag"]["category"] == vs.OST_MEPSpaceTags
              and readback["walls_exist"])
    val = _validate(out_path)
    _record(name, {
        "verb": "create", "category": "Space (RoomElem OST_MEPSpaces) + SpaceTag + Zone",
        "out": os.path.relpath(out_path, ROOT),
        "elements": {"walls": [w.elem_id for w in walls], "zone": zone.elem_id,
                     "space": space.elem_id, "tag": tag.elem_id,
                     "room_footprint_ft": [x0, y0, x1, y1], "point": [cx, cy]},
        "commit": {"elemtable_before": rep.elemtable_count_before,
                   "elemtable_after": rep.elemtable_count_after,
                   "watermark_after": rep.watermark_after,
                   "bytes_added": rep.per_seq_bytes_added},
        "verify_written": v, "structural_ok": sok,
        "readback": readback, "semantic_ok": sem_ok,
        "validate": val,
        "summary": (f"walls {[w.elem_id for w in walls]} + zone {zone.elem_id} + "
                    f"space {space.elem_id} 'ELECTRICAL ROOM' E101 + tag {tag.elem_id}; "
                    f"validator errors={val['n_errors']}"),
    })


# ===========================================================================
# MODIFY / DELETE an existing space
# ===========================================================================
def make_space_rename(name: str) -> None:
    out_path = os.path.join(SPACES_DIR, name)
    doc = Document.from_file(SRC)
    before = vs.describe_space(doc, SPACE_379575)
    plans = vs.rename_space(doc, SPACE_379575, name="ELEC EQUIP RM", number="128")
    rep = manipulate.commit_plans(SRC, out_path, plans)
    v = manipulate.verify_manipulated(out_path, edited_ids=[SPACE_379575])
    d = Document.from_file(out_path)
    after = vs.describe_space(d, SPACE_379575)
    val = _validate(out_path)
    _record(name, {
        "verb": "modify", "category": "Space (RoomElem)",
        "out": os.path.relpath(out_path, ROOT),
        "edit": {"space": SPACE_379575,
                 "before": {"name": before["name"], "number": before["number"]},
                 "after": {"name": after["name"], "number": after["number"]}},
        "commit": rep.to_json(), "verify_manipulated": v,
        "structural_ok": _structural_ok_manip(v),
        "semantic_ok": (after["name"] == "ELEC EQUIP RM" and after["number"] == "128"
                        and after["point"] == before["point"]),
        "validate": val,
        "summary": (f"space {SPACE_379575} {before['number']} {before['name']!r} -> "
                    f"{after['number']} {after['name']!r}; validator errors={val['n_errors']}"),
    })


def make_space_delete(name: str) -> None:
    out_path = os.path.join(SPACES_DIR, name)
    doc = Document.from_file(SRC)
    tags = vs.space_tags_of(doc, SPACE_379575)
    report = manipulate.dependency_report(doc, SPACE_379575)
    plan = vs.delete_space(doc, SPACE_379575, cascade=True)
    deleted = list(plan.ids_to_remove)
    rep = manipulate.commit_plans(SRC, out_path, [plan])
    v = manipulate.verify_manipulated(out_path, deleted_ids=deleted,
                                       edited_ids=[e for e in plan.edited_ids
                                                   if e not in set(deleted)])
    d = Document.from_file(out_path)
    space_gone = not d.exists(SPACE_379575)
    tags_gone = [t for t in tags if not d.exists(t)]
    # the zone's member list must no longer mention the space
    zone_members_after = None
    for zid in d.ids_of_class("ZoneElement"):
        zvv = d.value(zid) or {}
        if SPACE_379575 in (zvv.get("m_spaceIds") or []):
            zone_members_after = zid
    val = _validate(out_path)
    _record(name, {
        "verb": "delete", "category": "Space (RoomElem)",
        "out": os.path.relpath(out_path, ROOT),
        "edit": {"space": SPACE_379575, "its_tags": tags,
                 "closure_deleted": deleted,
                 "n_referrers_neutralised": len(getattr(plan, "referrer_edits", []) or []),
                 "dependency_report_kinds": sorted({str(k) for k in report})},
        "commit": rep.to_json(), "verify_manipulated": v,
        "structural_ok": _structural_ok_manip(v),
        "semantic_ok": space_gone and set(tags) <= set(tags_gone) and zone_members_after is None,
        "readback": {"space_gone": space_gone, "tags_gone": tags_gone,
                     "zone_still_listing_space": zone_members_after},
        "validate": val,
        "summary": (f"space {SPACE_379575} + tags {tags} deleted ({len(deleted)} in "
                    f"closure); zone member list neutralised={zone_members_after is None}; "
                    f"validator errors={val['n_errors']}"),
    })


# ===========================================================================
MAKERS = {
    "panel_schedule_view.rvt": lambda: make_panel_schedule_view(
        "panel_schedule_view.rvt", out_of_date=True),
    "panel_schedule_view_current.rvt": lambda: make_panel_schedule_view(
        "panel_schedule_view_current.rvt", out_of_date=False),
    "panel_schedule_view_rename.rvt": lambda: make_schedule_view_rename(
        "panel_schedule_view_rename.rvt"),
    "panel_schedule_view_delete.rvt": lambda: make_schedule_view_delete(
        "panel_schedule_view_delete.rvt"),
    "space_create.rvt": lambda: make_space_create("space_create.rvt"),
    "space_rename.rvt": lambda: make_space_rename("space_rename.rvt"),
    "space_delete.rvt": lambda: make_space_delete("space_delete.rvt"),
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    todo = argv or list(MAKERS)
    os.makedirs(SPACES_DIR, exist_ok=True)
    t0 = time.time()
    for name in todo:
        if name not in MAKERS:
            print(f"unknown proof {name!r}; choose from {sorted(MAKERS)}")
            return 2
        print(f"\n=== {name} ===")
        try:
            MAKERS[name]()
        except Exception as exc:                      # keep going; record the failure
            traceback.print_exc()
            RESULTS["files"][name] = {"status": "BLOCKED",
                                      "error": f"{type(exc).__name__}: {exc}"}
    RESULTS["seconds"] = round(time.time() - t0, 1)
    # cell table
    table = []
    for fn, e in RESULTS["files"].items():
        table.append({"file": fn, "verb": e.get("verb"), "category": e.get("category"),
                      "status": e.get("status"),
                      "structural_ok": e.get("structural_ok"),
                      "semantic_ok": e.get("semantic_ok"),
                      "validator_errors": (e.get("validate") or {}).get("n_errors"),
                      "validator_warnings": (e.get("validate") or {}).get("n_warnings")})
    RESULTS["cell_table"] = table
    mpath = os.path.join(HERE, "manifest.json")
    with open(mpath, "w") as fh:
        json.dump(RESULTS, fh, indent=1, default=str)
    spath = os.path.join(SPACES_DIR, "manifest.json")
    with open(spath, "w") as fh:
        json.dump({k: RESULTS["files"][k] for k in RESULTS["files"]
                   if k.startswith("space_")}, fh, indent=1, default=str)
    print("\n" + json.dumps(table, indent=1))
    print(f"\nmanifest -> {mpath}\ntotal {RESULTS['seconds']}s")
    return 0 if all(t["status"] == "VALIDATES" for t in table) else 1


if __name__ == "__main__":
    sys.exit(main())

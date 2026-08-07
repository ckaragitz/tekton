"""Regenerate docs/writer/specimens/*.json (mutation-planner).

Joins each specimen element across the three partition record streams
(seq 101 ElementHeader / 102 object / 103 rep), attaches its labelled
40-byte Global/ElemTable ElemRec and its ElementId reference closure.

Run:  RVT_SEG_CACHE=<dir> .venv/bin/python docs/writer/specimens/make_specimens.py
"""
import json
import os
import struct
import sys

ROOT = "/Users/ck/dev/things/rev-revit"
sys.path.insert(0, os.path.join(ROOT, "src"))
from rvt.mutate import Document, _collect_ids          # noqa: E402
from rvt.objects import _prune                          # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))

BIC = {-2000011: "OST_Walls", -2000023: "OST_Doors", -2000014: "OST_Windows",
       -2000240: "OST_Levels", -2000220: "OST_Grids", -2000160: "OST_Rooms",
       -2003600: "OST_MEPSpaces", -2001040: "OST_ElectricalEquipment",
       -2001060: "OST_ElectricalFixtures", -2001120: "OST_LightingFixtures",
       -2008037: "OST_ElectricalCircuit(sys)"}

SPECS = {
    "racbasicsampleproject": {
        "rac_level_311_Level1": (311, "Level 'Level 1' (project datum, elev 0 ft); type LevelAttributes 305"),
        "rac_level_245423_Level2": (245423, "Level 'Level 2', elev 9.8425 ft = 3.0 m"),
        "rac_levelattr_305": (305, "LevelAttributes type shared by the project levels"),
        "rac_grid_195169_1": (195169, "Grid '1' (type GridAttributes 341)"),
        "rac_wall_422243_SWall": (422243, "Straight SWall, base 311 top 694, type 198367, hosts door 422466"),
        "rac_walltype_198367_BasicWallType": (198367, "BasicWallType 'Wall - Timber Clad'"),
        "rac_door_422466_FamilyInstance": (422466, "Door in wall 422243, symbol 490150 (clone), master 232780, family 218942"),
        "rac_doorsymbol_490150_FamilySymbol": (490150, "Per-host cut clone symbol of the door"),
        "rac_doorfamily_218942_Family": (218942, "Family 'Single-Flush'"),
        "rac_room_857346_RoomElem": (857346, "RoomElem on Level 1"),
    },
    "rmebasicsampleproject": {
        "rme_level_378117_Level1": (378117, "rme host Level 1"),
        "rme_panel_581483_FamilyInstance": (581483, "Panelboard instance, face-hosted on SketchPlane 581481, symbol 470440 (master 455409)"),
        "rme_panelsymbol_470440_FamilySymbol": (470440, "the panel's symbol"),
        "rme_panelfamily_454674_Family": (454674, "M_Lighting and Appliance Panelboard - 208V MLO - Surface"),
        "rme_panelhost_581481_SketchPlane": (581481, "SketchPlane hosting panels 581482-581485"),
        "rme_circuit_469428_RbsElectricalSystem": (469428, "Circuit: 9 receptacles + panel 581483"),
        "rme_fixture_467291_FamilyInstance": (467291, "M_Duplex Receptacle : Standard on circuit 469428"),
        "rme_space_379575_RoomElem": (379575, "MEP Space containing the panels"),
        "rme_connectorelem_766662": (766662, "ConnectorElem inside an embedded family document (not in ElemTable)"),
    },
}


def elemrec_json(doc, eid):
    r = doc.et_by_id.get(eid)
    if r is None:
        return {"found_in_ElemTable": False}
    raw = struct.pack("<QIIIQQI", r.original_id, r.creation_ep, r.modified_ep,
                      r.user_modified_ep, r.id, r.owner_id, r.partition_id)
    return {"found_in_ElemTable": True, "raw_40_bytes_hex": raw.hex(" "),
            "fields": {
                "+0 u64 m_history.m_originalElementId": r.original_id,
                "+8 u32 m_history.m_creationDate (EpisodeId)": r.creation_ep,
                "+12 u32 m_history.m_lastModificationDate (EpisodeId)": r.modified_ep,
                "+16 u32 m_history.m_lastUserModificationDate": r.user_modified_ep,
                "+20 u64 m_id": r.id,
                "+28 u64 m_OwningElementId": (r.owner_id if r.owner_id != 0xFFFFFFFFFFFFFFFF else -1),
                "+36 u32 m_partitionId": r.partition_id}}


def specimen(doc, eid, note=""):
    out = {"element_id": eid, "note": note, "elemtable": elemrec_json(doc, eid)}
    refs = []
    for seq in (101, 102, 103):
        rec = doc.record(eid, seq)
        if rec is None:
            out[f"seq{seq}"] = None
            continue
        o = doc.dec.decode_record(rec.class_id, rec.payload)
        hlen = 12 if seq == 101 else 16
        out[f"seq{seq}"] = {
            "seq": seq, "segment_offset": rec.seg_offset, "header_bytes": hlen,
            "framing": ("i64 id + u32 psize + payload + u32 psize" if seq == 101
                        else "i64 id + u32 stamp + u32 psize + payload + u32 psize"),
            "elem_id": rec.elem_id, "stamp": None if seq == 101 else rec.stamp,
            "psize": rec.body_size, "class_id_hex": f"{rec.class_id:#06x}",
            "object_bytes": rec.body_size - 2, "total_record_bytes": hlen + rec.body_size + 4,
            "size_trailer_ok": rec.trailer_ok, "payload_head_hex": rec.payload[:32].hex(" "),
            "class": o.class_name, "clean": o.clean,
            "consumed_of_object": f"{o.consumed}/{o.total}",
            "value": _prune(o.value, max_list=60),
        }
        if o.errors:
            out[f"seq{seq}"]["errors"] = o.errors
        if seq == 101 and o.clean:
            cat = o.value.get("m_categroryId")
            out["category"] = {"id": cat, "builtin": BIC.get(cat, "?")}
            out["classDef"] = ((o.value.get("m_classDef") or {}).get("m_ref") or {}).get("classref")
        local = []
        _collect_ids(o.value, local)
        refs += [(seq, p, v) for p, v in local]
    closure, seen = [], set()
    for seq, p, v in refs:
        if (p, v) in seen:
            continue
        seen.add((p, v))
        closure.append({"from_seq": seq, "path": p, "id": v,
                        "target_class": doc.class_of(v),
                        "in_ElemTable": v in doc.et_by_id,
                        "in_partitions": doc.record(v) is not None})
    out["references"] = closure
    return out


if __name__ == "__main__":
    for project, specs in SPECS.items():
        doc = Document.load(project)
        for name, (eid, note) in specs.items():
            with open(os.path.join(OUT, name + ".json"), "w") as fh:
                json.dump(specimen(doc, eid, note), fh, indent=1, default=str)
            print("wrote", name)

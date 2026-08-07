#!/usr/bin/env python3
"""make_devices.py — build the ELECTRICAL DEVICES proof files (MEP: devices).

Every file is written by the real writer (rvt.commit.commit_new_elements for
creation, rvt.manipulate.commit_plans for edits/deletes), then proven three
ways: (1) the writer's structural verify (CRC / ECC / walker / stamps /
counts / sentinels), (2) a semantic READBACK (re-open with
Document.from_file and check the device fields), (3) the Autodesk-free
validator ``tools/rvt_validate.py`` (structure + consistency + semantic,
incl. reference integrity, connector-graph symmetry and circuit invariants) —
ZERO errors required; the ``--strict`` circuit-ready gate is recorded too.

Files (all in this directory, template = the Revit MEP sample):

  receptacle_wall_hosted.rvt   CREATE wall devices — Standard duplex receptacle
                               (DummyPlaneRef work plane coincident with the face,
                               the pattern 416/424 corpus receptacles use), a
                               single-pole switch SHARING that plane, and a GFCI
                               receptacle on another wall via a GeomOnPlaneRef
                               face reference.  Mounting heights + Marks set.
  light_ceiling_hosted.rvt     CREATE ceiling fixtures — two recessed troffers on
                               one NEW down-facing ceiling plane (the 410/410
                               corpus pattern) + a pendant light hung on an
                               EXISTING ceiling plane.
  floor_device.rvt             CREATE floor devices — a floor receptacle on a
                               level-DATUM work plane (OnDatumPlaneRef -> Level 1)
                               + a free-standing 15 kVA dry transformer (free /
                               level-based pattern).
  multi_load_circuit.rvt       CIRCUIT over MULTIPLE loads — a new 208 V panel on
                               an existing electrical-room plane + 4 new
                               receptacles on two walls + ONE 20 A/120 V branch
                               circuit tying all 4 to the panel (connector graph
                               closes both ways; panel slot allocated).
  device_modify_move.rvt       MODIFY / MOVE / RETYPE / RE-HOST existing devices —
                               Mark set, slid along its wall + mounting height
                               raised, Standard -> GFCI retype, and a receptacle
                               re-hosted onto another wall's plane.
  device_delete.rvt            DELETE existing devices — a circuited receptacle
                               (circuit + wire refs neutralised, host plane kept)
                               and a tagged pendant light (cascade takes its tags).

Run from the repo root:
    .venv/bin/python experiments/mep/devices/make_devices.py
Results -> experiments/mep/devices/manifest.json (per-file cell verdicts).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.commit import commit_new_elements, verify_written  # noqa: E402
from rvt.mutate import Document  # noqa: E402
from rvt import manipulate as M  # noqa: E402
from rvt.mep import devices as D  # noqa: E402
from rvt.validate import validate_file  # noqa: E402

SRC = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")


def _template_document_guid() -> str:
    """The template's own Unique Document GUID (== its History entry[0]).

    ``commit_new_elements`` runs the G2 identity scrub, which by default
    mints a FRESH document GUID; but the minimal commit does not add a
    History episode, so the validator's L2 invariant "BasicFileInfo Unique
    Document GUID == History entry[0]" then fails.  For these element-level
    proofs we keep the template's GUID (self-consistent, validator-clean);
    the finding is filed in docs/inbox/mep-devices.md for the identity /
    save-history streams (the real fix = record a new History episode).
    """
    from rvt.container import open_rvt
    from rvt import stream_encoders as se
    with open_rvt(SRC) as f:
        return se.decode_basic_file_info(f.raw("BasicFileInfo"))["unique_document_guid"]


IDENTITY = {"document_guid": _template_document_guid()}

# ---------------------------------------------------------------------------
# rme template constants (electrical room "28 Technology", Level 1)
# ---------------------------------------------------------------------------
LEVEL1 = 378117          # 'Level 1'  z 0.309 ft
LEVEL2 = 378118          # 'Level 2'  z 12.467 ft
ROOM_POINT = (64.0, 110.0)          # inside room 573809 / space 379575
WALL_EAST = 573325       # east wall of the room (x 69.24, N->S) — room-side face x 68.916
WALL_NORTH = 573607      # north wall (y 125.67, W->E)
WALL_PARTITION = 573609  # interior partition y 113.49 across the room
WALL_WEST = 573608       # west wall (x 59.07) — the sample's own panels hang here
PLANE_ELEC_ROOM = 581481  # existing DummyPlaneRef work plane on the west wall face

# loaded symbols (from the sample's own content)
RECEP_STD = 342654       # M_Duplex Receptacle :: Standard
RECEP_GFCI = 342652      # M_Duplex Receptacle :: GFCI
SWITCH_1P = 343624       # M_Lighting Switches :: Single Pole
TROFFER = 365612         # M_Plain Recessed Lighting Fixture :: 600x600 - 277
PENDANT = 446386         # M_Pendant Light - Linear - 2 Lamp :: 1200mm - 277V
PANEL_208 = 470440       # M_Lighting and Appliance Panelboard - 208V MLO :: 400 A
XFMR_15KVA = 621990      # M_Dry Type Transformer - 480-208Y120 :: 15 kVA
CEILING_PLANE_EXISTING = 442678   # existing down-facing ceiling plane (75 pendants)

# existing devices (for the edit / delete proofs)
EX_RECEP_MARK = 467473        # receptacle on plane 452560 (partition north face)
EX_RECEP_MOVE = 467523        # receptacle on plane 453884 (east wall face)
EX_RECEP_RETYPE = 467480      # receptacle on plane 467517 (north wall face) -> GFCI
EX_RECEP_REHOST = 467456      # receptacle on plane 467294 (west wall) -> east wall plane
EX_RECEP_DELETE = 467291      # circuited receptacle (circuit 469428 + 2 wires)
EX_LIGHT_DELETE = 444176      # tagged pendant light on circuit 473648


# ===========================================================================
# planners  (each returns doc, roles{name: id}, extra info)
# ===========================================================================
def plan_receptacle_wall():
    doc = Document.from_file(SRC)
    # R-101: Standard receptacle on the east wall's ROOM-side face, 18" AFF,
    # via a new DummyPlaneRef work plane coincident with the face
    sp1, r1 = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST,
                                distance_along_ft=18.0, elevation_ft=1.5,
                                facing_point=ROOM_POINT, plane_ref="dummy",
                                mark="R-101")
    # S-101: a single-pole switch SHARING that plane, 44" AFF
    s1 = D.add_wall_device(doc, SWITCH_1P, wall=WALL_EAST,
                           distance_along_ft=22.0, elevation_ft=3.65,
                           sketchplane=sp1, mark="S-101")[0]
    # R-102: GFCI on the partition's room-side (south) face, counter height,
    # via a true GeomOnPlaneRef face reference into the wall
    sp2, r2 = D.add_wall_device(doc, RECEP_GFCI, wall=WALL_PARTITION,
                                distance_along_ft=3.0, elevation_ft=3.5,
                                facing_point=(64.0, 108.0), plane_ref="geom",
                                mark="R-102")
    roles = {"plane_dummy": sp1.elem_id, "receptacle_std": r1.elem_id,
             "switch": s1.elem_id, "plane_geom": sp2.elem_id,
             "receptacle_gfci": r2.elem_id}
    return doc, roles, {
        "cells": [["receptacle", "CREATE"], ["switch", "CREATE"]],
        "proves": ("Standard receptacle on a NEW DummyPlaneRef work plane "
                   "coincident with the east wall's room-side face (the pattern "
                   "416/424 corpus receptacles use), a single-pole switch SHARING "
                   "that plane, and a GFCI receptacle on the interior partition "
                   "via a GeomOnPlaneRef face reference (tag 5). Mounting heights "
                   "(1.5 / 3.65 / 3.5 ft above Level 1) and Marks R-101/S-101/"
                   "R-102 set; room/space + native header parents populated."),
    }


def plan_light_ceiling():
    doc = Document.from_file(SRC)
    # two troffers on ONE new down-facing ceiling plane under ceiling 580538
    # (its underside is at z 20.51 ft, a Level-2 ceiling)
    cp, t1 = D.add_light_fixture(doc, TROFFER, (62.0, 110.0), ceiling_z_ft=20.51,
                                 mark="L-201")
    t2 = D.add_light_fixture(doc, TROFFER, (66.0, 110.0), ceiling_plane=cp,
                             rotation=0.0, mark="L-202")[0]
    # a pendant hung on an EXISTING ceiling plane (75 real pendants share it),
    # scheduled to Level 2 like the sample's own pendants on that plane
    # (explicit level_id — the plane sits at z 11.48, just under Level 2)
    p1 = D.add_light_fixture(doc, PENDANT, (64.5, 114.0),
                             ceiling_plane=CEILING_PLANE_EXISTING, level_id=LEVEL2,
                             mark="L-203")[0]
    roles = {"ceiling_plane_new": cp.elem_id, "troffer_1": t1.elem_id,
             "troffer_2": t2.elem_id, "pendant_on_existing_plane": p1.elem_id}
    return doc, roles, {
        "cells": [["lighting_fixture", "CREATE"]],
        "proves": ("two recessed troffers hosted on ONE new horizontal DOWN-FACING "
                   "DummyPlaneRef ceiling plane at z 20.51 ft (the underside of "
                   "ceiling 580538; the 410/410 corpus pattern — no reference into "
                   "the Ceiling element) plus a pendant light on the EXISTING "
                   "ceiling plane 442678. Frames: Z = (0,0,-1); scheduling level = "
                   "Level 2; Marks set."),
    }


def plan_floor_device():
    doc = Document.from_file(SRC)
    fp, fd = D.add_floor_device(doc, RECEP_STD, (64.0, 118.0), LEVEL1, mark="R-FLR-1")
    xf = D.add_floor_device(doc, XFMR_15KVA, (66.5, 118.5), LEVEL1,
                            hosting_mode="free", mark="T-DEV-1")[0]
    roles = {"datum_plane": fp.elem_id, "floor_receptacle": fd.elem_id,
             "free_transformer": xf.elem_id}
    return doc, roles, {
        "cells": [["floor_device", "CREATE"]],
        "proves": ("a floor receptacle work-plane-hosted on a NEW SketchPlane whose "
                   "OnDatumPlaneRef references LEVEL 1 (m_datumPlaneId=378117 — the "
                   "pattern face-based families use when placed on a level; specimen "
                   "579920-579923 on plane 573289), plus a genuinely FREE-STANDING "
                   "15 kVA dry-type transformer (m_hostId -1, level-based; the "
                   "624416 pattern)."),
    }


def plan_multi_load_circuit():
    doc = Document.from_file(SRC)
    # panel: 208V MLO 400 A on the EXISTING electrical-room plane (the plane
    # the sample's own four panels hang on), above them at 4.3 ft
    panel = D.add_device_on_plane(doc, PANEL_208, PLANE_ELEC_ROOM,
                                  xyz=(59.256, 118.5, 4.3), level_id=LEVEL1,
                                  mark="LP-DEV1", kind="panel")
    # 4 receptacles: two on the north wall, two on the east wall (room-side)
    spN, r1 = D.add_wall_device(doc, RECEP_STD, wall=WALL_NORTH,
                                distance_along_ft=31.5, elevation_ft=1.5,
                                facing_point=ROOM_POINT, mark="R-1")
    r2 = D.add_wall_device(doc, RECEP_STD, wall=WALL_NORTH,
                           distance_along_ft=35.5, elevation_ft=1.5,
                           sketchplane=spN, mark="R-2")[0]
    spE, r3 = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST,
                                distance_along_ft=8.0, elevation_ft=1.5,
                                facing_point=ROOM_POINT, mark="R-3")
    r4 = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST,
                           distance_along_ft=12.0, elevation_ft=1.5,
                           sketchplane=spE, mark="R-4")[0]
    circ = D.add_multi_load_circuit(doc, panel, [r1, r2, r3, r4],
                                    number="1", description="RECEPTACLES RM 28",
                                    rating=20.0, poles=1, voltage_v=120.0,
                                    apparent_load_va_per_load=180.0,
                                    load_classification="Receptacles")
    roles = {"panel": panel.elem_id, "plane_north": spN.elem_id,
             "plane_east": spE.elem_id, "receptacle_1": r1.elem_id,
             "receptacle_2": r2.elem_id, "receptacle_3": r3.elem_id,
             "receptacle_4": r4.elem_id, "circuit": circ.elem_id}
    return doc, roles, {
        "cells": [["circuit_multi_load", "CREATE"], ["panelboard", "CREATE"],
                  ["receptacle", "CREATE"]],
        "proves": ("ONE 20 A / 120 V branch circuit carrying FOUR new receptacles "
                   "(2 on the north wall + 2 on the east wall of the electrical "
                   "room, on two shared new work planes) fed from a NEW 208 V "
                   "panelboard hosted on the existing electrical-room plane 581481: "
                   "the circuit owns 4 load connectors (connType 1 -> each "
                   "receptacle's supply connector) + a FINAL base connector "
                   "(connType 4 -> the panel's 50000-series slot); every load and "
                   "the panel back-link the circuit (connType 4); "
                   "m_baseConnectorIdArray = {self, LAST}; path node 0 = the panel."),
    }


def plan_modify_move():
    doc = Document.from_file(SRC)
    plans = []
    plans.append(D.set_device_mark(doc, EX_RECEP_MARK, "R-EDITED"))
    plans.append(D.move_device_along_host(doc, EX_RECEP_MOVE, along_ft=2.0, up_ft=0.5))
    plans.append(D.retype_device(doc, EX_RECEP_RETYPE, RECEP_GFCI))
    plans.extend(D.rehost_device(doc, EX_RECEP_REHOST, 453884, uv=(-14.0, 3.5)))
    roles = {"mark_target": EX_RECEP_MARK, "move_target": EX_RECEP_MOVE,
             "retype_target": EX_RECEP_RETYPE, "rehost_target": EX_RECEP_REHOST,
             "rehost_new_plane": 453884}
    return doc, plans, roles, {
        "cells": [["receptacle", "MODIFY"], ["receptacle", "MOVE"],
                  ["receptacle", "RETYPE"]],
        "proves": ("edits to EXISTING devices in the user's model: Mark of receptacle "
                   f"{EX_RECEP_MARK} set to 'R-EDITED'; receptacle {EX_RECEP_MOVE} slid "
                   "+2.0 ft along its wall and raised +0.5 ft (mounting height) — a "
                   f"move WITHIN its host plane; receptacle {EX_RECEP_RETYPE} retyped "
                   f"Standard -> GFCI; receptacle {EX_RECEP_REHOST} re-hosted from the "
                   "west-wall plane onto the east-wall plane 453884 (host id + frame + "
                   "header parents swapped)."),
    }


def plan_delete():
    doc = Document.from_file(SRC)
    p1 = D.delete_device(doc, EX_RECEP_DELETE, cascade=True)
    p2 = D.delete_device(doc, EX_LIGHT_DELETE, cascade=True)
    plans = [p1, p2]
    roles = {"deleted_receptacle": EX_RECEP_DELETE, "deleted_light": EX_LIGHT_DELETE,
             "removed_ids": sorted(set(p1.ids_to_remove) | set(p2.ids_to_remove)),
             "referrers_neutralised": [r["id"] for r in (p1.referrer_edits + p2.referrer_edits)]}
    return doc, plans, roles, {
        "cells": [["receptacle", "DELETE"], ["lighting_fixture", "DELETE"]],
        "proves": (f"DELETE of the circuited receptacle {EX_RECEP_DELETE} (its "
                   "circuit's member connector, the two wires drawn to it and the "
                   "panel bookkeeping are neutralised; its shared host plane and its "
                   f"circuit stay) and of the tagged pendant light {EX_LIGHT_DELETE} "
                   "(cascade removes its two IndependentTags; its circuit / wires are "
                   "neutralised). No dangling reference survives."),
    }


# ===========================================================================
# readbacks
# ===========================================================================
def _mark_of(doc, eid):
    v = doc.value(eid) or {}
    ps = ((((v.get("m_pParamValueSetAString") or {}).get("value") or {}).get("m_paramSet")) or [])
    for p in ps:
        if isinstance(p, dict) and p.get("m_paramId") == D.BIP_ALL_MODEL_MARK:
            return p.get("m_value")
    return None


def _inst_readback(doc, eid):
    v = doc.value(eid) or {}
    ii = ((v.get("m_pInstanceInfo") or {}).get("value")) or {}
    dpm = ((v.get("m_pDesignPropManager") or {}).get("value") or {})
    hid = v.get("m_hostId")
    host_flavour = None
    if isinstance(hid, int) and hid > 0 and doc.class_of(hid) == "SketchPlane":
        host_flavour = D._plane_flavour(doc, hid)
    return {"id": eid, "class": doc.class_of(eid), "category": doc.category_of(eid),
            "m_hostId": hid, "host_flavour": host_flavour,
            "m_workPlaneBased": v.get("m_workPlaneBased"),
            "m_assocLevelId": v.get("m_assocLevelId"),
            "m_scheduleOnlyLevelId": v.get("m_scheduleOnlyLevelId"),
            "symbol": ii.get("m_symbolId"), "master": v.get("m_masterSymbolId"),
            "trf": ii.get("m_Trf"), "mark": _mark_of(doc, eid),
            "space": dpm.get("m_idSpace"), "room": dpm.get("m_idRoom")}


def _plane_readback(doc, pid):
    sp = doc.value(pid) or {}
    pref = sp.get("m_oPlaneRef") or {}
    pv = pref.get("value") or {}
    out = {"id": pid, "class": doc.class_of(pid), "planeref": pref.get("ptr_class"),
           "trf": (sp.get("m_oTrf") or {}).get("value")}
    if pref.get("ptr_class") == "GeomOnPlaneRef":
        gr = pv.get("m_geomRef") or {}
        out["geomRef"] = {"m_elemId": gr.get("m_elemId"), "m_geomTag": gr.get("m_geomTag")}
    if pref.get("ptr_class") == "OnDatumPlaneRef":
        out["datumPlaneId"] = pv.get("m_datumPlaneId")
    if pref.get("ptr_class") == "DummyPlaneRef":
        pl = (pv.get("m_pPlane") or {}).get("value") or {}
        out["plane"] = {"origin": pl.get("m_origin"), "xVec": pl.get("m_xVec"),
                        "yVec": pl.get("m_yVec")}
    return out


def _connrefs(doc, eid):
    v = doc.value(eid) or {}
    out = {}
    for c in (Document._conn_manager(v) or {}).get("m_connPtrArray") or []:
        cv = c.get("value") or {}
        out[cv.get("m_nIndex")] = cv.get("m_arrRefs")
    return out


def _readback_new(path, roles):
    d = Document.from_file(path)
    rb = {}
    for name, eid in roles.items():
        if not isinstance(eid, int):
            continue
        cls = d.class_of(eid)
        if cls == "SketchPlane":
            rb[name] = _plane_readback(d, eid)
        elif cls == "RbsElectricalSystem":
            v = d.value(eid) or {}
            rb[name] = {"id": eid, "class": cls, "number": v.get("m_number"),
                        "rating": v.get("m_dRating"), "poles": v.get("m_nPoles"),
                        "voltage_internal": v.get("m_dVoltage"),
                        "apparent_load_internal": v.get("m_dApparentLoad"),
                        "load_classification": v.get("m_strLoadClassifications"),
                        "baseConnectorIdArray": v.get("m_baseConnectorIdArray"),
                        "connectors": _connrefs(d, eid),
                        "path_node0": (v.get("m_pathNodes") or [{}])[0]}
        else:
            rb[name] = _inst_readback(d, eid)
            if D.OST_ElectricalEquipment == d.category_of(eid) or name == "panel":
                rb[name]["connectors"] = _connrefs(d, eid)
            else:
                rb[name]["connectors"] = _connrefs(d, eid)
    return d, rb


def _circuit_graph_ok(d, circ_id, panel_id, load_ids):
    """The connector graph closes exactly like the real 4-load circuit."""
    v = d.value(circ_id) or {}
    conns = (Document._conn_manager(v) or {}).get("m_connPtrArray") or []
    if len(conns) != len(load_ids) + 1:
        return False, f"circuit has {len(conns)} connectors, want {len(load_ids) + 1}"
    got_loads = []
    last = conns[-1].get("value") or {}
    lrefs = last.get("m_arrRefs") or []
    if not (lrefs and lrefs[0].get("m_id") == panel_id and lrefs[0].get("m_connType") == 4
            and (lrefs[0].get("m_nIndex") or 0) >= 50000):
        return False, f"base connector does not point at panel {panel_id} slot: {lrefs}"
    slot = lrefs[0]["m_nIndex"]
    last_idx = last.get("m_nIndex")
    bca = v.get("m_baseConnectorIdArray") or []
    if bca != [{"m_id": circ_id, "m_nIndex": last_idx, "m_connType": 4}]:
        return False, f"baseConnectorIdArray {bca} != {{self,{last_idx},4}}"
    # each load connector -> its load with connType 1, and the load links back
    for c in conns[:-1]:
        cv = c.get("value") or {}
        refs = cv.get("m_arrRefs") or []
        if not refs or refs[0].get("m_connType") != 1:
            return False, f"load connector {cv.get('m_nIndex')} refs {refs}"
        lid, lconn = refs[0]["m_id"], refs[0]["m_nIndex"]
        got_loads.append(lid)
        back = None
        for lc in (Document._conn_manager(d.value(lid) or {}) or {}).get("m_connPtrArray") or []:
            lcv = lc.get("value") or {}
            if lcv.get("m_nIndex") == lconn:
                back = lcv.get("m_arrRefs") or []
        if not any(b.get("m_id") == circ_id and b.get("m_nIndex") == cv.get("m_nIndex")
                   and b.get("m_connType") == 4 for b in (back or [])):
            return False, f"load {lid} conn {lconn} does not link back to circuit: {back}"
    if sorted(got_loads) != sorted(load_ids):
        return False, f"loads on circuit {got_loads} != planned {load_ids}"
    # panel slot back-link
    pback = None
    for pc in (Document._conn_manager(d.value(panel_id) or {}) or {}).get("m_connPtrArray") or []:
        pcv = pc.get("value") or {}
        if pcv.get("m_nIndex") == slot:
            pback = pcv.get("m_arrRefs") or []
    if not any(b.get("m_id") == circ_id and b.get("m_nIndex") == last_idx
               and b.get("m_connType") == 4 for b in (pback or [])):
        return False, f"panel {panel_id} slot {slot} does not link back to circuit: {pback}"
    node0 = (v.get("m_pathNodes") or [{}])[0]
    if node0.get("m_elemId") not in (panel_id, None):
        return False, f"path node 0 elemId {node0.get('m_elemId')} != panel {panel_id}"
    return True, (f"graph closes: {len(load_ids)} loads (connType 1, back-linked "
                  f"connType 4), base = panel {panel_id} slot {slot}, "
                  f"baseConnectorIdArray = {{self,{last_idx}}}, pathNode0 = panel")


# ===========================================================================
# validation gate
# ===========================================================================
def _validate(path):
    rep = validate_file(path)
    out = {"ok_zero_errors": bool(rep.ok),
           "errors": [f.message for f in rep.errors],
           "warnings": [f.message for f in rep.warnings],
           "stats": {k: rep.stats.get(k) for k in
                     ("records", "elements_decoded", "decode_failures",
                      "refs_checked", "connector_edges", "circuits")}}
    try:
        srep = validate_file(path, strict=True)
        out["strict_ok"] = bool(srep.ok)
        out["strict_errors"] = [f.message for f in srep.errors]
    except TypeError:
        out["strict_ok"] = None
    return out


# ===========================================================================
# builders
# ===========================================================================
def _build_create(name, planner, manifest, checks_fn=None):
    t0 = time.time()
    doc, roles, info = planner()
    elements = list(doc.new_elements)
    dangling = {e.elem_id: doc.check_references(e) for e in elements}
    records = [dict(doc.serialize(e)) for e in elements]
    plans = [e.elemrec for e in elements]
    out_path = os.path.join(HERE, name)
    rep = commit_new_elements(SRC, out_path, records, plans, identity=IDENTITY)
    ids = [e.elem_id for e in elements]
    v = verify_written(out_path, ids)
    clean = {s: sum(1 for x in v["new_ids_found"][s].values() if x["clean"])
             for s in (101, 102, 103)}
    structural = (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
                  and v["walker_errors"] == 0 and v["stamps_ok"]
                  and all(n == len(ids) for n in clean.values())
                  and v["elemtable_count"] == v["header_count"]
                  and all(v["sentinel_last"].values()))
    d2, rb = _readback_new(out_path, roles)
    semantic_ok, semantic_note = (True, "")
    if checks_fn is not None:
        semantic_ok, semantic_note = checks_fn(d2, roles, rb)
    val = _validate(out_path)
    entry = {
        "file": os.path.relpath(out_path, ROOT), "kind": "create",
        "cells": info["cells"], "proves": info["proves"],
        "size_bytes": os.path.getsize(out_path),
        "elements": [{"id": e.elem_id, "kind": e.kind, "class": e.class_name,
                      "template": e.template_id, "notes": e.notes} for e in elements],
        "roles": roles,
        "dangling_refs_before_write": {str(k): v for k, v in dangling.items()},
        "elemtable": {"before": rep.elemtable_count_before, "after": rep.elemtable_count_after},
        "verify_written": {"crc_failures": v["crc_failures"], "ecc_mismatches": v["ecc_mismatches"],
                           "walker_errors": v["walker_errors"], "stamps_ok": v["stamps_ok"],
                           "new_records_clean_per_seq": clean,
                           "counts_match": v["elemtable_count"] == v["header_count"],
                           "sentinels_last": all(v["sentinel_last"].values())},
        "readback": rb,
        "semantic_check": {"ok": bool(semantic_ok), "note": semantic_note},
        "validator": val,
        "STRUCTURALLY_VALID": bool(structural),
        "VALIDATES_ZERO_ERRORS": bool(val["ok_zero_errors"]),
        "SEMANTIC_OK": bool(semantic_ok),
        "seconds": round(time.time() - t0, 1),
    }
    entry["ALL_OK"] = entry["STRUCTURALLY_VALID"] and entry["VALIDATES_ZERO_ERRORS"] \
        and entry["SEMANTIC_OK"] and not any(dangling.values())
    manifest["files"].append(entry)
    _print_entry(name, entry)
    return entry["ALL_OK"]


def _build_edit(name, planner, manifest, checks_fn):
    t0 = time.time()
    doc, plans, roles, info = planner()
    out_path = os.path.join(HERE, name)
    plan_json = [p.to_json() for p in plans]
    edited = sorted({i for p in plans for i in (getattr(p, "edited_ids", None) or [])})
    deleted = sorted({i for p in plans for i in (getattr(p, "ids_to_remove", None) or [])})
    rep = M.commit_plans(SRC, out_path, plans)
    v = M.verify_manipulated(out_path, deleted_ids=deleted, edited_ids=[
        i for i in edited if i not in deleted])
    structural = (v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
                  and v["walker_errors"] == 0 and v["isize_identity_mismatches"] == 0
                  and v["stamps_ok"] and all(v["sentinel_last"].values())
                  and v["elemtable_count"] == v["header_count"]
                  and not v["deleted_still_present"] and not v["deleted_in_elemtable"]
                  and v["unit0_ids_equal_elemtable"] and v["elemtable_ids_sorted"])
    d2 = Document.from_file(out_path)
    semantic_ok, semantic_note, rb = checks_fn(d2, roles)
    val = _validate(out_path)
    entry = {
        "file": os.path.relpath(out_path, ROOT), "kind": "edit",
        "cells": info["cells"], "proves": info["proves"],
        "size_bytes": os.path.getsize(out_path),
        "roles": roles, "plans": plan_json,
        "elemtable": {"before": rep.elemtable_count_before, "after": rep.elemtable_count_after},
        "verify_manipulated": {"crc_failures": v["crc_failures"], "ecc_mismatches": v["ecc_mismatches"],
                               "walker_errors": v["walker_errors"],
                               "isize_identity_mismatches": v["isize_identity_mismatches"],
                               "stamps_ok": v["stamps_ok"],
                               "sentinels_last": all(v["sentinel_last"].values()),
                               "counts_match": v["elemtable_count"] == v["header_count"],
                               "deleted_still_present": v["deleted_still_present"],
                               "deleted_in_elemtable": v["deleted_in_elemtable"],
                               "unit0_ids_equal_elemtable": v["unit0_ids_equal_elemtable"],
                               "edited": v["edited"]},
        "readback": rb,
        "semantic_check": {"ok": bool(semantic_ok), "note": semantic_note},
        "validator": val,
        "STRUCTURALLY_VALID": bool(structural),
        "VALIDATES_ZERO_ERRORS": bool(val["ok_zero_errors"]),
        "SEMANTIC_OK": bool(semantic_ok),
        "seconds": round(time.time() - t0, 1),
    }
    entry["ALL_OK"] = entry["STRUCTURALLY_VALID"] and entry["VALIDATES_ZERO_ERRORS"] \
        and entry["SEMANTIC_OK"]
    manifest["files"].append(entry)
    _print_entry(name, entry)
    return entry["ALL_OK"]


def _print_entry(name, e):
    print(f"\n=== {name}")
    for c in e["cells"]:
        print(f"  cell {c[0]:20s} {c[1]}")
    print(f"  ElemTable {e['elemtable']['before']} -> {e['elemtable']['after']}")
    vv = e.get("verify_written") or e.get("verify_manipulated")
    print(f"  structural: CRC {vv['crc_failures']} ECC {vv['ecc_mismatches']} "
          f"walker {vv['walker_errors']} stamps {vv['stamps_ok']} "
          f"-> {'OK' if e['STRUCTURALLY_VALID'] else 'FAIL'}")
    val = e["validator"]
    print(f"  rvt_validate: {'0 ERRORS' if val['ok_zero_errors'] else 'ERRORS ' + str(val['errors'])} "
          f"(strict circuit-ready: {val.get('strict_ok')}); warnings={len(val['warnings'])}")
    print(f"  semantic readback: {'OK' if e['SEMANTIC_OK'] else 'FAIL'} — "
          f"{e['semantic_check']['note'][:300]}")
    print(f"  >>> {'ALL OK' if e['ALL_OK'] else 'CHECK FAILED'}  ({e['seconds']}s)")


# ===========================================================================
# semantic checks per file
# ===========================================================================
def _chk_recept(d, roles, rb):
    problems = []
    r1, s1, r2 = rb["receptacle_std"], rb["switch"], rb["receptacle_gfci"]
    pd, pg = rb["plane_dummy"], rb["plane_geom"]
    for r, pl, mark, cat in ((r1, roles["plane_dummy"], "R-101", D.OST_ElectricalFixtures),
                             (s1, roles["plane_dummy"], "S-101", D.OST_LightingDevices),
                             (r2, roles["plane_geom"], "R-102", D.OST_ElectricalFixtures)):
        if r["class"] != "FamilyInstance" or r["m_hostId"] != pl:
            problems.append(f"{r['id']} not hosted on plane {pl} (host {r['m_hostId']})")
        if r["m_workPlaneBased"] is not True or r["m_assocLevelId"] != -1 \
                or r["m_scheduleOnlyLevelId"] != LEVEL1:
            problems.append(f"{r['id']} placement flags wrong: {r}")
        if r["mark"] != mark:
            problems.append(f"{r['id']} mark {r['mark']!r} != {mark!r}")
        if r["category"] != cat:
            problems.append(f"{r['id']} category {r['category']} != {cat}")
        if r["space"] != 379575 or r["room"] != 573809:
            problems.append(f"{r['id']} space/room {r['space']}/{r['room']} != 379575/573809")
    if pd["planeref"] != "DummyPlaneRef":
        problems.append(f"dummy plane {pd}")
    if pg["planeref"] != "GeomOnPlaneRef" or pg.get("geomRef", {}).get("m_elemId") != WALL_PARTITION \
            or pg.get("geomRef", {}).get("m_geomTag") not in (5, 6):
        problems.append(f"geom plane {pg}")
    # the two devices on the dummy plane share it and its normal is horizontal (wall)
    t = pd.get("trf") or {}
    z = D._columns_from_rows(t.get("m_3x3"))[2] if t.get("m_3x3") else (0, 0, 1)
    if abs(z[2]) > 1e-6:
        problems.append(f"wall plane normal not horizontal: {z}")
    if abs((r1["trf"] or {}).get("m_or", [0, 0, 0])[2] - (D._level_elevation(d, LEVEL1) + 1.5)) > 1e-6:
        problems.append("receptacle mounting height != 1.5 ft above Level 1")
    return (not problems), ("wall devices verified: shared DummyPlaneRef plane "
                             f"{roles['plane_dummy']} (receptacle+switch), GeomOnPlaneRef "
                             f"plane {roles['plane_geom']} -> wall {WALL_PARTITION} (GFCI); "
                             "hosting flags, mounting heights, marks, category, "
                             "space/room all correct" if not problems else "; ".join(problems))


def _chk_light(d, roles, rb):
    problems = []
    cp = rb["ceiling_plane_new"]
    if cp["planeref"] != "DummyPlaneRef":
        problems.append(f"ceiling plane {cp}")
    z = D._columns_from_rows((cp.get("trf") or {}).get("m_3x3"))[2]
    if abs(z[2] + 1.0) > 1e-6:
        problems.append(f"ceiling plane normal {z} is not (0,0,-1)")
    if abs((cp.get("trf") or {}).get("m_or", [0, 0, 0])[2] - 20.51) > 1e-6:
        problems.append("ceiling plane not at z 20.51")
    for key, pl, mark in (("troffer_1", roles["ceiling_plane_new"], "L-201"),
                          ("troffer_2", roles["ceiling_plane_new"], "L-202"),
                          ("pendant_on_existing_plane", CEILING_PLANE_EXISTING, "L-203")):
        r = rb[key]
        if r["class"] != "FamilyInstance" or r["m_hostId"] != pl:
            problems.append(f"{key} {r['id']} host {r['m_hostId']} != {pl}")
        if r["m_workPlaneBased"] is not True or r["m_assocLevelId"] != -1 \
                or r["m_scheduleOnlyLevelId"] != LEVEL2:
            problems.append(f"{key} placement flags wrong: {r}")
        if r["category"] != D.OST_LightingFixtures:
            problems.append(f"{key} category {r['category']}")
        if r["mark"] != mark:
            problems.append(f"{key} mark {r['mark']!r} != {mark!r}")
        m3 = (r["trf"] or {}).get("m_3x3")
        zz = D._columns_from_rows(m3)[2] if m3 else None
        if zz is None or abs(zz[2] + 1.0) > 1e-6:
            problems.append(f"{key} frame Z {zz} is not down (0,0,-1)")
    return (not problems), ("ceiling fixtures verified: 2 troffers on new down-facing "
                             f"ceiling plane {roles['ceiling_plane_new']} (z 20.51, Z=(0,0,-1)), "
                             f"pendant on existing plane {CEILING_PLANE_EXISTING}; all schedule "
                             "to Level 2, frames point down, marks set"
                             if not problems else "; ".join(problems))


def _chk_floor(d, roles, rb):
    problems = []
    fp = rb["datum_plane"]
    if fp["planeref"] != "OnDatumPlaneRef" or fp.get("datumPlaneId") != LEVEL1:
        problems.append(f"datum plane {fp} does not reference Level 1")
    fd = rb["floor_receptacle"]
    if fd["m_hostId"] != roles["datum_plane"] or fd["m_workPlaneBased"] is not True:
        problems.append(f"floor receptacle not on datum plane: {fd}")
    if fd["mark"] != "R-FLR-1":
        problems.append(f"floor receptacle mark {fd['mark']}")
    xf = rb["free_transformer"]
    if xf["m_hostId"] not in (-1, None) or xf["m_workPlaneBased"] is not False:
        problems.append(f"transformer not free/level-based: {xf}")
    if xf["m_assocLevelId"] != LEVEL1:
        problems.append(f"free transformer assocLevel {xf['m_assocLevelId']} != {LEVEL1}")
    if xf["category"] != D.OST_ElectricalEquipment:
        problems.append(f"transformer category {xf['category']}")
    z1 = D._level_elevation(d, LEVEL1)
    if abs((fd["trf"] or {}).get("m_or", [0, 0, 9])[2] - z1) > 1e-6:
        problems.append("floor receptacle not at the level elevation")
    return (not problems), (f"floor devices verified: receptacle on OnDatumPlaneRef plane "
                             f"{roles['datum_plane']} -> Level 1; free transformer (hostId -1, "
                             "workPlaneBased False, assocLevel = Level 1); marks set"
                             if not problems else "; ".join(problems))


def _chk_circuit(d, roles, rb):
    problems = []
    ok, note = _circuit_graph_ok(d, roles["circuit"], roles["panel"],
                                 [roles[f"receptacle_{i}"] for i in (1, 2, 3, 4)])
    if not ok:
        problems.append(note)
    c = rb["circuit"]
    if abs((c.get("rating") or 0) - 20.0) > 1e-9 or c.get("poles") != 1 \
            or c.get("number") != "1" or c.get("load_classification") != "Receptacles":
        problems.append(f"circuit values wrong: {c}")
    want_v = 120.0 * D.INTERNAL_PER_SI
    want_va = 4 * 180.0 * D.INTERNAL_PER_SI
    if abs((c.get("voltage_internal") or 0) - want_v) > 1e-6 \
            or abs((c.get("apparent_load_internal") or 0) - want_va) > 1e-6:
        problems.append(f"voltage/load internal units wrong: {c.get('voltage_internal')} "
                        f"{c.get('apparent_load_internal')} (want {want_v} {want_va})")
    pnl = rb["panel"]
    if pnl["m_hostId"] != PLANE_ELEC_ROOM or pnl["mark"] != "LP-DEV1" \
            or pnl["category"] != D.OST_ElectricalEquipment:
        problems.append(f"panel wrong: {pnl}")
    for i in (1, 2, 3, 4):
        r = rb[f"receptacle_{i}"]
        if r["category"] != D.OST_ElectricalFixtures or r["m_workPlaneBased"] is not True:
            problems.append(f"receptacle_{i} wrong: {r}")
    return (not problems), (note + "; circuit 20 A / 1 P / #1 / 'Receptacles', "
                             "120 V and 4x180 VA in internal units; panel on plane "
                             f"{PLANE_ELEC_ROOM} marked LP-DEV1"
                             if not problems else "; ".join(problems))


def _chk_modify(d, roles):
    problems, rb = [], {}
    src = Document.from_file(SRC)
    # mark
    rb["mark"] = {"id": roles["mark_target"], "mark": _mark_of(d, roles["mark_target"]),
                  "before": _mark_of(src, roles["mark_target"])}
    if rb["mark"]["mark"] != "R-EDITED":
        problems.append(f"mark not applied: {rb['mark']}")
    # move: +2 ft along the wall (plane X) and +0.5 ft up
    before = M.instance_placement(src, roles["move_target"])
    after = M.instance_placement(d, roles["move_target"])
    fr = D.plane_frame(src, before["m_hostId"])
    dv = [after["m_or"][i] - before["m_or"][i] for i in range(3)]
    along = sum(dv[i] * fr["X"][i] for i in range(3))
    up = sum(dv[i] * fr["Y"][i] for i in range(3))
    off = sum(dv[i] * fr["Z"][i] for i in range(3))
    rb["move"] = {"id": roles["move_target"], "before_or": before["m_or"], "after_or": after["m_or"],
                  "delta_along_ft": round(along, 6), "delta_up_ft": round(up, 6),
                  "delta_off_plane_ft": round(off, 6), "host_kept": after["m_hostId"] == before["m_hostId"]}
    if abs(along - 2.0) > 1e-6 or abs(up - 0.5) > 1e-6 or abs(off) > 1e-6 or not rb["move"]["host_kept"]:
        problems.append(f"move wrong: {rb['move']}")
    # retype
    pl_after = M.instance_placement(d, roles["retype_target"])
    rb["retype"] = {"id": roles["retype_target"], "symbol_after": pl_after["m_symbolId"],
                    "master_after": pl_after["m_masterSymbolId"]}
    if pl_after["m_symbolId"] != RECEP_GFCI or pl_after["m_masterSymbolId"] != RECEP_GFCI:
        problems.append(f"retype not applied: {rb['retype']}")
    # rehost
    rh_before = M.instance_placement(src, roles["rehost_target"])
    rh_after = M.instance_placement(d, roles["rehost_target"])
    fr2 = D.plane_frame(d, roles["rehost_new_plane"])
    dd = [rh_after["m_or"][i] - fr2["or"][i] for i in range(3)]
    off2 = sum(dd[i] * fr2["Z"][i] for i in range(3))
    hdr = d.value(roles["rehost_target"], 101) or {}
    dele = ((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion") or []
    rb["rehost"] = {"id": roles["rehost_target"], "host_before": rh_before["m_hostId"],
                    "host_after": rh_after["m_hostId"], "or_after": rh_after["m_or"],
                    "off_new_plane_ft": round(off2, 6),
                    "old_plane_in_deletion": rh_before["m_hostId"] in dele,
                    "new_plane_in_deletion": roles["rehost_new_plane"] in dele,
                    "frame_matches_new_plane": rh_after["m_3x3"] == [list(r) for r in D._rows_from_columns(fr2["X"], fr2["Y"], fr2["Z"])]}
    if rh_after["m_hostId"] != roles["rehost_new_plane"] or abs(off2) > 1e-6 \
            or rb["rehost"]["old_plane_in_deletion"] or not rb["rehost"]["new_plane_in_deletion"] \
            or not rb["rehost"]["frame_matches_new_plane"]:
        problems.append(f"rehost wrong: {rb['rehost']}")
    return (not problems), ("edits verified: mark 'R-EDITED' present; move = +2.000 ft along wall "
                             "X, +0.500 ft up, 0 off-plane, host kept; retype -> GFCI 342652 "
                             "(symbol+master); re-host -> plane 453884 (host id, frame = plane "
                             "frame, mounting point ON the plane, header deletion swapped)"
                             if not problems else "; ".join(problems)), rb


def _chk_delete(d, roles):
    problems, rb = [], {}
    src = Document.from_file(SRC)
    removed = set(roles["removed_ids"])
    still = [i for i in removed if d.exists(i)]
    rb["removed_ids"] = sorted(removed)
    rb["still_present"] = still
    if still:
        problems.append(f"deleted ids still present: {still}")
    # no surviving record may still mention a removed id (byte-level referrer scan)
    left = M.candidate_referrers(d, removed)
    left = {k: v for k, v in left.items() if k not in removed}
    rb["surviving_mentions"] = {str(k): v for k, v in list(left.items())[:10]}
    if left:
        # decode-verified referrers only (candidate scan is byte-first)
        real = M.referrers(d, removed)
        rb["surviving_real_referrers"] = {str(k): v.get("class") for k, v in real.items()}
        if real:
            problems.append(f"surviving referrers still reference deleted ids: {list(real)[:6]}")
    # the receptacle's host plane and its circuit survive; the circuit's
    # member connector that pointed at the receptacle now points at nothing
    circ = 469428
    rb["circuit_469428_conn_refs_after"] = _connrefs(d, circ)
    if not d.exists(circ):
        problems.append("circuit 469428 was deleted (should be a surviving peer)")
    if not d.exists(467294):
        problems.append("shared host plane 467294 was deleted (should stay)")
    for j, refs in (rb["circuit_469428_conn_refs_after"] or {}).items():
        for r in refs or []:
            if r.get("m_id") in removed:
                problems.append(f"circuit 469428 conn {j} still references deleted {r.get('m_id')}")
    # the light's tags were cascaded
    rb["light_tags_gone"] = [i for i in (535118, 535457) if not d.exists(i)]
    if len(rb["light_tags_gone"]) != 2:
        problems.append(f"light 444176 tags 535118/535457 not both removed: {rb['light_tags_gone']}")
    return (not problems), (f"deletes verified: {sorted(removed)} absent from all seqs + "
                             "ElemTable; circuit 469428 and host plane 467294 survive; the "
                             "circuit's member connector no longer references the receptacle; "
                             "wires/panel/light-circuit referrers neutralised; the light's 2 "
                             "IndependentTags removed by cascade; no surviving reference to any "
                             "deleted id"
                             if not problems else "; ".join(problems)), rb


# ===========================================================================
def main() -> int:
    manifest = {"template": os.path.relpath(SRC, ROOT), "stream": "mep-devices",
                "files": []}
    ok = True
    started = time.time()
    for name, planner, chk in (
        ("receptacle_wall_hosted.rvt", plan_receptacle_wall, _chk_recept),
        ("light_ceiling_hosted.rvt", plan_light_ceiling, _chk_light),
        ("floor_device.rvt", plan_floor_device, _chk_floor),
        ("multi_load_circuit.rvt", plan_multi_load_circuit, _chk_circuit),
    ):
        try:
            ok &= _build_create(name, planner, manifest, chk)
        except Exception:
            traceback.print_exc()
            manifest["files"].append({"file": name, "error": traceback.format_exc(), "ALL_OK": False})
            ok = False
    for name, planner, chk in (
        ("device_modify_move.rvt", plan_modify_move, _chk_modify),
        ("device_delete.rvt", plan_delete, _chk_delete),
    ):
        try:
            ok &= _build_edit(name, planner, manifest, chk)
        except Exception:
            traceback.print_exc()
            manifest["files"].append({"file": name, "error": traceback.format_exc(), "ALL_OK": False})
            ok = False
    manifest["all_ok"] = bool(ok)
    manifest["seconds"] = round(time.time() - started, 1)
    with open(os.path.join(HERE, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, default=str)
    print("\nwrote", os.path.join(HERE, "manifest.json"))
    print("ALL OK" if ok else "SOME CHECK FAILED — see manifest.json")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

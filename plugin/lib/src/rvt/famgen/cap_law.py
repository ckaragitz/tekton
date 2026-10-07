"""Cap law (#1030): a face lock witnesses the cap that lies on its plane.

An extrusion's cap TAGS follow its own Start / End parameters, in every born
extrusion: tag 0 = the cap at the End offset, tag 1 = the cap at the Start
offset (117 / 118 born boxes whose End is above their Start rebuild with
every face and edge tag equal, counts only).  ``height_law`` locks "end"
(tag 0) to the higher plane and "start" (tag 1) to the lower one, as born
files do.  So the cached solid must carry tag 0 on the cap at the higher
plane, or every such lock names the opposite cap.

:func:`lock_face_findings` reads a built document the way a reviewer would:
for every ``Alignment`` witness on an ``ExtrusionElem`` it finds the cached
face with the witnessed tag and compares its elevation with the witness's own
segment.  It reports facts about the file, never that Revit flexes it
(hard rule 4).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

EPS = 1e-6


def horizontal_cap_z(rep: Optional[dict]) -> Dict[int, float]:
    """``{face tag: z}`` of every horizontal planar face of a cached solid."""
    out: Dict[int, float] = {}
    for sn in (rep or {}).get("m_subNodes") or []:
        for f in (sn.get("value") or {}).get("m_pFaces") or []:
            fv = f.get("value") or {}
            sv = (fv.get("m_pSurf") or {}).get("value") or {}
            x, y = sv.get("m_xVec"), sv.get("m_yVec")
            if not (x and y and sv.get("m_origin")):
                continue
            nz = x[0] * y[1] - x[1] * y[0]
            if abs(abs(nz) - 1.0) < 1e-9:
                out[int(fv["m_GInfo"]["m_tag"])] = float(sv["m_origin"][2])
    return out


def lock_face_findings(doc: Any) -> List[Dict[str, Any]]:
    """One row per ``Alignment`` witness on an ``ExtrusionElem`` cap:
    ``{lock, extrusion, tag, witness_z, face_z, on_plane}``.  A witness whose
    tag is not a horizontal cap of the cached solid (a side face, a curve) is
    not judged."""
    ext = {e.elem_id: e for e in doc.elements if e.class_name == "ExtrusionElem"}
    rows: List[Dict[str, Any]] = []
    for e in doc.elements:
        if e.class_name != "Alignment":
            continue
        for w in e.obj.get("m_witnessRefs") or []:
            g = ((w.get("m_pWitnessRef") or {}).get("value") or {}).get("m_geomRef") or {}
            x = ext.get(g.get("m_elemId"))
            ends = w.get("m_oldRefSegEnds") or []
            if x is None or not ends:
                continue
            tag = int(g.get("m_geomTag", -1))
            fz = horizontal_cap_z(x.rep).get(tag)
            if fz is None:
                continue
            wz = float(ends[0][2])
            rows.append({"lock": e.elem_id, "extrusion": x.elem_id, "tag": tag,
                         "witness_z": wz, "face_z": fz, "on_plane": abs(fz - wz) < EPS})
    return rows

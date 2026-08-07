"""hosting.py — mount FamilyInstances ON WALL FACES (face-hosting).

MEP equipment (panelboards, receptacles, switches) is not free-standing in a
real Revit model: it is *work-plane based* and hosted on a ``SketchPlane``
element (``FamilyInstance.m_hostId = <SketchPlane id>``,
``m_workPlaneBased = True``).  This module reproduces Autodesk's own
face-hosting pattern, decoded from the ``rmebasicsampleproject`` corpus
(see ``docs/writer/hosting.md`` for the full evidence):

* A wall-FACE-bound SketchPlane carries ``m_oPlaneRef`` of class
  ``GeomOnPlaneRef`` whose ``m_geomRef = {m_elemId: <wall id>,
  m_geomTag: <face tag>, m_subTag: -1}``.  The face tag is a SMALL STABLE
  integer produced by the wall's geometry generator, not a GUID:
  ``5`` = the side face on the -leftNormal side ("right of the drawing
  direction" = INTERIOR for an unflipped wall), ``6`` = the +leftNormal
  side (EXTERIOR).  (leftNormal = the location line direction rotated
  +90 deg: (-dy, dx).)  Verified on 13 wall-face SketchPlanes over 3 wall
  types; the wall's own solid faces carry ``m_GInfo.m_tag`` 5 / 6 / 7
  (bottom) / 14 (top) / 10,18 (ends).
* The SketchPlane's frame (``m_oTrf``, a column-major 3x3 + origin) is
  the standard Revit vertical-face frame: **Z = the face's OUTWARD
  normal, Y = world +Z (up), X = up x Z**, origin = a point on the face
  plane at the wall's base elevation.  A hosted instance's placement
  ``Trf`` is the SAME frame (its origin = the mounting point ON the face,
  z = mounting height).  Byte-identical to instances 742670 (480 V panel
  on plane 623305 / wall 573590), 460372/460229 (receptacles on both faces
  of wall 573738), etc.
* Header parents: SketchPlane ``m_deletion = [wall, self]``,
  ``m_regenOnly = [wall_type]``; the hosted instance keeps the SketchPlane
  in its own ``m_deletion`` and lists the WALL in ``m_regenOnly``;
  ``m_assocLevelId = -1``, ``m_scheduleOnlyLevelId = <level>``.

Two hosting flavours are provided:

``plane_ref="geom"`` (default) — a true face reference into the wall
    (``GeomOnPlaneRef``): the panel is associated to the wall (Revit
    reports the wall as the host; moving the wall carries the panel).
``plane_ref="dummy"`` — a ``DummyPlaneRef`` work plane made COINCIDENT
    with the wall face but carrying NO reference to the wall (this is how
    218 of the 240 hosting SketchPlanes in the rme sample work, including
    the catalogued panels 581482-581485 on plane 581481, which sits exactly
    on wall 573608's face).  The panel is physically flush-mounted on the
    face but "<not associated>"; it never depends on the wall's geometry
    being regenerated, so it is the guaranteed-safe fallback for panels on
    walls that are themselves created in the same run.

Public API (each returns planned :class:`rvt.mutate.NewElement` objects;
serialize + write them exactly like walls/instances, e.g. via
``rvt.commit.commit_new_elements``)::

    from rvt.mutate import Document
    from rvt import hosting

    doc  = Document.load("rmebasicsampleproject")           # or Document.from_file(...)
    wall = 573608                                            # an EXISTING wall id ...
    # ... or a wall you just planned:  wall = doc.add_wall(level, wtype, p0, p1)
    sp   = hosting.add_sketchplane_on_wall(doc, wall, side="interior",
                                            at_point_ft=(59.3, 118.0))
    sp, inst = hosting.host_instance_on_wall(doc, symbol_id=619617, wall=wall,
                                             distance_along_ft=8.0,
                                             elevation_ft=4.0, side="interior")

``side`` accepts ``'interior' | 'exterior'`` (== ``'right' | 'left'`` of
the wall's drawing direction, Revit convention for an unflipped wall) or a
face tag ``5 | 6``.  Because MEP intent is "the face that looks into the
room", prefer :func:`side_facing_point` with a point inside the room.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple, Union

from .mutate import (CLASS_ELEMENT_HEADER, CLASS_SERIALIZED_DUMMY, Document,
                     NewElement)

__all__ = [
    "WallFaceGeom", "wall_geometry", "face_frame", "side_facing_point",
    "add_sketchplane_on_wall", "host_instance_on_wall",
    "find_face_sketchplane_template", "reconstruct_plane_trf",
    "FACE_TAG_INTERIOR", "FACE_TAG_EXTERIOR",
]

#: seq-102 class of SketchPlane (schema type id in Revit 2026; also read
#: dynamically from the template record so other releases still work)
CLASS_SKETCHPLANE = 0x0F5D

#: Wall solid side-face geometry tags (m_GInfo.m_tag on the wall's cached
#: GElement faces; the ids GeomOnPlaneRef.m_geomRef.m_geomTag points at).
#: tag 5 = side face on the -leftNormal side (RIGHT of the drawing direction
#: = interior for an unflipped wall); tag 6 = the +leftNormal side face
#: (LEFT of direction = exterior).  Also seen: 7 bottom, 14 top, 10/18 ends.
FACE_TAG_INTERIOR = 5
FACE_TAG_EXTERIOR = 6

_SIDE_ALIASES = {
    "interior": FACE_TAG_INTERIOR, "int": FACE_TAG_INTERIOR,
    "right": FACE_TAG_INTERIOR, "inside": FACE_TAG_INTERIOR,
    "exterior": FACE_TAG_EXTERIOR, "ext": FACE_TAG_EXTERIOR,
    "left": FACE_TAG_EXTERIOR, "outside": FACE_TAG_EXTERIOR,
}


# ---------------------------------------------------------------------------
# wall geometry (works for an EXISTING wall id AND a planned NewElement)
# ---------------------------------------------------------------------------
@dataclass
class WallFaceGeom:
    """A wall's location-line geometry, resolved for face hosting."""
    wall_id: int
    start: Tuple[float, float, float]     # location line start (ft, world)
    dir: Tuple[float, float]              # unit direction (xy)
    length: float                         # ft
    thickness: float                      # ft (0.0 if unknown -> centerline hosting)
    base_z: float                         # wall base elevation (ft)
    left_normal: Tuple[float, float]      # (-dy, dx): +leftNormal side = exterior/tag 6
    wall_type_id: Optional[int]
    level_id: Optional[int]
    is_new: bool                          # the wall is itself planned in this run

    def face_tag(self, side: Union[str, int]) -> int:
        return _resolve_side(side)

    def face_normal(self, side: Union[str, int]) -> Tuple[float, float, float]:
        """OUTWARD unit normal of the requested side face."""
        s = 1.0 if self.face_tag(side) == FACE_TAG_EXTERIOR else -1.0
        return (s * self.left_normal[0], s * self.left_normal[1], 0.0)

    def face_offset(self, side: Union[str, int]) -> float:
        """Signed offset of the face plane from the location line, along
        +leftNormal (exterior +half, interior -half)."""
        s = 1.0 if self.face_tag(side) == FACE_TAG_EXTERIOR else -1.0
        return s * (self.thickness / 2.0)

    def point_on_face(self, side: Union[str, int], distance_along_ft: float,
                      z: Optional[float] = None) -> Tuple[float, float, float]:
        """World point on the face plane, ``distance_along_ft`` from the
        wall's start point along its direction, at absolute elevation ``z``
        (default: the wall base)."""
        off = self.face_offset(side)
        nx, ny = self.left_normal
        x = self.start[0] + self.dir[0] * distance_along_ft + nx * off
        y = self.start[1] + self.dir[1] * distance_along_ft + ny * off
        return (x, y, self.base_z if z is None else float(z))

    def project_to_face(self, side, point) -> Tuple[float, float, float]:
        """Project a world point onto the face plane (keeps its z)."""
        px, py = float(point[0]), float(point[1])
        pz = float(point[2]) if len(point) > 2 else self.base_z
        along = (px - self.start[0]) * self.dir[0] + (py - self.start[1]) * self.dir[1]
        return self.point_on_face(side, along, pz)


def _resolve_side(side: Union[str, int]) -> int:
    if isinstance(side, int) and not isinstance(side, bool):
        if side in (FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR):
            return side
        raise ValueError(f"face tag must be {FACE_TAG_INTERIOR} (interior) or "
                         f"{FACE_TAG_EXTERIOR} (exterior), got {side}")
    key = str(side).strip().lower()
    if key not in _SIDE_ALIASES:
        raise ValueError(f"unknown wall side {side!r}: use interior/exterior "
                         f"(right/left of the wall direction) or a face tag")
    return _SIDE_ALIASES[key]


def _wall_id_and_obj(doc: Document, wall) -> Tuple[int, dict, bool]:
    """Resolve ``wall`` (an existing element id OR a planned NewElement) to
    (id, decoded seq-102 object, is_new)."""
    if isinstance(wall, NewElement):
        if wall.kind != "wall":
            raise TypeError(f"NewElement {wall.elem_id} is a {wall.kind!r}, not a wall")
        return wall.elem_id, wall.obj, True
    wid = int(wall)
    for e in doc.new_elements:                     # a wall planned earlier in this run
        if e.elem_id == wid:
            if e.kind != "wall":
                raise TypeError(f"element {wid} planned in this run is not a wall")
            return wid, e.obj, True
    if not doc.exists(wid):
        raise LookupError(f"wall {wid} does not exist in template {doc.project}")
    cls = doc.class_of(wid)
    if cls not in ("SWall", "VWall", "Wall", "HostObj"):
        raise TypeError(f"element {wid} is a {cls!r}, not a wall")
    obj = doc.value(wid)
    if not obj:
        raise LookupError(f"wall {wid} did not decode cleanly")
    return wid, obj, False


def wall_geometry(doc: Document, wall) -> WallFaceGeom:
    """Location line, thickness, base elevation and side normals of a wall.

    ``wall`` may be an EXISTING wall's element id or a wall planned in this
    same session (:class:`rvt.mutate.NewElement` from ``Document.add_wall`` /
    its id) — the electrical-room case where the room's walls are created
    in the same run as the panels mounted on them.
    """
    wid, obj, is_new = _wall_id_and_obj(doc, wall)
    told = Document._wall_geometry(obj)               # start(x,y,z), dir(xy), faces
    start = tuple(float(c) for c in told["start"])
    if len(start) < 3:
        start = (start[0], start[1], 0.0)
    d = (float(told["dir"][0]), float(told["dir"][1]))
    n = math.hypot(d[0], d[1]) or 1.0
    d = (d[0] / n, d[1] / n)
    thick = Document._wall_thickness(told) or 0.0
    base_z = float(start[2])
    lvl = obj.get("m_assocLevelId")
    if isinstance(lvl, int) and lvl > 0 and not doc.exists(lvl):
        lvl = None
    return WallFaceGeom(
        wall_id=wid, start=(start[0], start[1], base_z), dir=d,
        length=float(told["length"]), thickness=float(thick), base_z=base_z,
        left_normal=(-d[1], d[0]),
        wall_type_id=obj.get("m_WallAttributesId"),
        level_id=lvl if isinstance(lvl, int) and lvl > 0 else None,
        is_new=is_new)


def side_facing_point(doc: Document, wall, point) -> int:
    """The face tag (5 interior / 6 exterior) of the side of ``wall`` that
    FACES the world point ``point`` (e.g. the centroid of the room the
    equipment serves).  This is the robust way to say "mount on the room
    side" without relying on interior/exterior orientation conventions."""
    g = wall_geometry(doc, wall)
    sx, sy, _ = g.start
    nx, ny = g.left_normal
    d = (float(point[0]) - sx) * nx + (float(point[1]) - sy) * ny
    return FACE_TAG_EXTERIOR if d >= 0 else FACE_TAG_INTERIOR


# ---------------------------------------------------------------------------
# the canonical vertical-face frame
# ---------------------------------------------------------------------------
_UP = (0.0, 0.0, 1.0)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def face_frame(g: WallFaceGeom, side: Union[str, int], origin) -> dict:
    """The Revit vertical-face placement frame for the given side.

    Column vectors: **X = up x n, Y = up (+Z), Z = n = the face's OUTWARD
    normal**; ``origin`` = a point on the face plane.  The archive stores
    ``Trf.m_3x3`` COLUMN-major (rows below are (X.i, Y.i, Z.i)) — verified
    byte-for-byte against SketchPlanes 623305/625865/595054/593910 and the
    instances hosted on them.  Returns the dict shapes used by both the
    SketchPlane ``m_oTrf`` and the instance ``InstanceInfo.m_Trf``.
    """
    n = g.face_normal(side)
    x = _cross(_UP, n)                     # X = up x normal (lies along the wall)
    y = _UP
    m3 = [[x[0], y[0], n[0]],
          [x[1], y[1], n[1]],
          [x[2], y[2], n[2]]]
    org = [float(origin[0]), float(origin[1]), float(origin[2])]
    return {"m_3x3": m3, "m_or": org, "x": x, "y": y, "n": n}


def reconstruct_plane_trf(doc: Document, sketchplane_id: int) -> Optional[dict]:
    """Recompute a real wall-face SketchPlane's ``m_oTrf`` from its host
    wall + face tag using :func:`face_frame` — the validation used by the
    test-suite (predicted 3x3 == stored 3x3 on every corpus specimen)."""
    sv = doc.value(sketchplane_id) or {}
    pref = sv.get("m_oPlaneRef") or {}
    if pref.get("ptr_class") != "GeomOnPlaneRef":
        return None
    gr = ((pref.get("value") or {}).get("m_geomRef") or {})
    wid, tag = gr.get("m_elemId"), gr.get("m_geomTag")
    if not (isinstance(wid, int) and wid > 0) or tag not in (FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR):
        return None
    if doc.class_of(wid) not in ("SWall", "VWall", "Wall"):
        return None
    stored = ((sv.get("m_oTrf") or {}).get("value") or {})
    g = wall_geometry(doc, wid)
    fr = face_frame(g, tag, stored.get("m_or") or [0, 0, 0])
    return {"predicted": fr["m_3x3"], "stored": stored.get("m_3x3"),
            "origin": stored.get("m_or"), "wall": wid, "tag": tag}


# ---------------------------------------------------------------------------
# template discovery
# ---------------------------------------------------------------------------
def find_face_sketchplane_template(doc: Document, plane_ref: str = "geom",
                                   prefer_tag: Optional[int] = None) -> int:
    """A real hosting SketchPlane to clone.

    ``plane_ref="geom"``: a ``GeomOnPlaneRef`` plane bound to a WALL face
    (13 in the rme sample); ``plane_ref="dummy"``: a ``DummyPlaneRef`` work
    plane (218 in rme).  ``prefer_tag`` biases the geom choice to a plane
    already on that face tag (cosmetic — every field is rewritten anyway).
    """
    want = "GeomOnPlaneRef" if plane_ref == "geom" else "DummyPlaneRef"
    best = None
    for spid in doc.ids_of_class("SketchPlane"):
        sv = doc.value(spid) or {}
        pref = sv.get("m_oPlaneRef") or {}
        if pref.get("ptr_class") != want:
            continue
        if want == "GeomOnPlaneRef":
            gr = ((pref.get("value") or {}).get("m_geomRef") or {})
            wid = gr.get("m_elemId")
            if not (isinstance(wid, int) and wid > 0
                    and doc.class_of(wid) in ("SWall", "VWall", "Wall")):
                continue                       # bound to another instance, not a wall
            if prefer_tag is not None and gr.get("m_geomTag") == prefer_tag:
                return spid
            if best is None:
                best = spid
        else:
            pl = (((pref.get("value") or {}).get("m_pPlane") or {}).get("value"))
            if isinstance(pl, dict) and best is None:
                best = spid
    if best is None:
        raise LookupError(f"{doc.project}: no {want} SketchPlane specimen to clone "
                          "(template needs at least one work-plane / face-hosted "
                          "family instance)")
    return best


def _hosted_instance_template(doc: Document, symbol_id: int) -> Optional[int]:
    """Prefer cloning a REAL instance of ``symbol_id`` that is itself hosted
    on a SketchPlane (so m_workPlaneBased / m_scheduleOnlyLevelId / the
    parameter sets already have the face-hosted shape); wall-face-bound
    hosts (GeomOnPlaneRef) beat dummy planes.  None -> let
    ``Document._template_instance`` decide."""
    exact_geom, exact_any = [], []
    for i in doc.ids_of_class("FamilyInstance"):
        v = doc.value(i)
        if not v:
            continue
        ii = ((v.get("m_pInstanceInfo") or {}).get("value")) or {}
        if symbol_id not in (ii.get("m_symbolId"), v.get("m_masterSymbolId")):
            continue
        hid = v.get("m_hostId")
        if not (isinstance(hid, int) and hid > 0) or doc.class_of(hid) != "SketchPlane":
            continue
        exact_any.append(i)
        pref = ((doc.value(hid) or {}).get("m_oPlaneRef") or {})
        if pref.get("ptr_class") == "GeomOnPlaneRef":
            exact_geom.append(i)
    if exact_geom:
        return exact_geom[0]
    if exact_any:
        return exact_any[0]
    return None


# ---------------------------------------------------------------------------
# SketchPlane creation
# ---------------------------------------------------------------------------
def add_sketchplane_on_wall(doc: Document, wall, side: Union[str, int] = "interior",
                            at_point_ft=None, *, plane_ref: str = "geom",
                            template_id: Optional[int] = None) -> NewElement:
    """Plan a new ``SketchPlane`` lying on ``wall``'s ``side`` face.

    ``wall``: an existing wall id OR a wall planned in this run.  ``side``:
    'interior'|'exterior' ('right'|'left' of the drawing direction) or a
    face tag 5|6.  ``at_point_ft``: an optional world (x, y[, z]) that is
    projected onto the face to become the plane origin (default: the wall
    start on the face at the wall base).  ``plane_ref``: 'geom' (true face
    reference, ``GeomOnPlaneRef{m_elemId = wall, m_geomTag = 5|6}``) or
    'dummy' (a ``DummyPlaneRef`` work plane COINCIDENT with the face, no
    wall dependency — the safe fallback for a wall created in this run).
    """
    if plane_ref not in ("geom", "dummy"):
        raise ValueError("plane_ref must be 'geom' or 'dummy'")
    g = wall_geometry(doc, wall)
    tag = _resolve_side(side)
    tpl = template_id or find_face_sketchplane_template(doc, plane_ref, prefer_tag=tag)
    tval = doc.value(tpl)
    if not tval:
        raise LookupError(f"template SketchPlane {tpl} did not decode")
    eid = doc.next_id()

    # origin: the given point projected onto the face plane (its z kept),
    # else the wall start on the face at the wall base
    if at_point_ft is not None:
        origin = g.project_to_face(tag, at_point_ft)
    else:
        origin = g.point_on_face(tag, 0.0, g.base_z)
    fr = face_frame(g, tag, origin)

    obj = copy.deepcopy(tval)
    obj["m_id"] = eid
    obj["m_famId"] = -1
    obj["m_designOptionId"] = -1
    obj["m_createdPhaseId"] = -1
    obj["m_demolishedPhaseId"] = -1
    obj["m_locked"] = False
    obj["m_userId"] = -1
    obj["m_flipZ"] = False
    obj["m_oTrf"] = {"ptr_class": "Trf", "pid": -1,
                     "value": {"m_3x3": fr["m_3x3"], "m_or": fr["m_or"]}}

    pref = obj.get("m_oPlaneRef") or {}
    pv = pref.get("value") if isinstance(pref, dict) else None
    if plane_ref == "geom":
        if pref.get("ptr_class") != "GeomOnPlaneRef" or not isinstance(pv, dict):
            raise LookupError(f"template {tpl} has no GeomOnPlaneRef to rewrite")
        gr = pv.get("m_geomRef")
        if not isinstance(gr, dict):
            gr = {}
            pv["m_geomRef"] = gr
        gr.update({
            "m_intermediateTags": [],          # direct reference, no link chain
            "m_oNextRef": None,
            "m_elemId": g.wall_id,             # the WALL that owns the face
            "m_ownerDBViewId": -1,
            "m_foreignElemIdRef": {"m_id64": -1},
            "m_geomTag": tag,                  # 5 interior / 6 exterior side face
            "m_subTag": -1,
            "m_famMemberIdx": -1,
            "m_flags": 0,
            "m_isLazyRef": False,
        })
        pv["m_oRawPlaneInLinkCache"] = None
        pv["m_oFacePointRef"] = None
        pv["m_offset"] = [0.0, 0.0]           # plane sits ON the face
        pv["m_angle"] = 0.0
        pv["m_flip"] = False
        notes = [f"GeomOnPlaneRef -> wall {g.wall_id} face tag {tag} "
                 f"({'exterior/left' if tag == FACE_TAG_EXTERIOR else 'interior/right'}"
                 f" side); frame Z = outward normal {tuple(round(c, 4) for c in fr['n'])}"]
        if g.is_new:
            notes.append("host wall is created in this same run: the face "
                         "reference resolves when Revit regenerates the new "
                         "wall's solid (its side faces always carry tags 5/6); "
                         "fallback = plane_ref='dummy' if the translator "
                         "reports an unresolved sketch-plane face")
    else:                                                        # dummy plane
        if pref.get("ptr_class") != "DummyPlaneRef" or not isinstance(pv, dict):
            raise LookupError(f"template {tpl} has no DummyPlaneRef to rewrite")
        gr = pv.get("m_geomRef")
        if isinstance(gr, dict):
            gr.update({"m_intermediateTags": [], "m_oNextRef": None, "m_elemId": -1,
                       "m_ownerDBViewId": -1, "m_foreignElemIdRef": {"m_id64": -1},
                       "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
                       "m_flags": 0, "m_isLazyRef": False})
        plane = (pv.get("m_pPlane") or {}).get("value")
        if not isinstance(plane, dict):
            plane = {}
            pv["m_pPlane"] = {"ptr_class": "Plane", "pid": -1, "value": plane}
        plane["m_orientFlag"] = True
        plane["m_origin"] = list(fr["m_or"])
        plane["m_xVec"] = [float(c) for c in fr["x"]]      # X = up x n
        plane["m_yVec"] = [float(c) for c in fr["y"]]      # Y = up  (=> normal n)
        if not plane.get("m_Envelope"):
            plane["m_Envelope"] = {"m_corners": [[1.0, 1.0], [0.0, 0.0]]}
        notes = [f"DummyPlaneRef work plane COINCIDENT with wall {g.wall_id}'s face "
                 f"(tag {tag} side, outward normal {tuple(round(c, 4) for c in fr['n'])}); "
                 "no reference into the wall (panel is flush-mounted but "
                 "'<not associated>' — never depends on the wall's regeneration)"]

    # ---- seq 101 ElementHeader: parents = the wall (deletion + type) --------
    header = copy.deepcopy(doc.value(tpl, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = -1
    header["m_familyId"] = -1
    header["m_miscId"] = -1
    parents = ((header.get("m_parents") or {}).get("value")) or {}
    deletion = {eid}
    regen_only = []
    if plane_ref == "geom":
        deletion.add(g.wall_id)                       # deleting the wall deletes the plane
        if g.wall_type_id and g.wall_type_id > 0:
            regen_only = [g.wall_type_id]              # type change re-solves the face
    parents.update({
        "m_deletion": sorted(deletion),
        "m_regenOnly": regen_only,
        "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [], "m_appearanceParents": [],
        "m_deferredParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": False,
    })
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = parents
    header["m_pBBox"] = None                     # planes carry no bounding box

    rec = doc.record(tpl)
    class_id = rec.class_id if rec is not None else CLASS_SKETCHPLANE
    el = NewElement(eid, "sketchplane", "SketchPlane", class_id, header, obj,
                    None,                       # seq 103 = SerializedDummy (no cached geometry)
                    doc._new_elemrec(eid), tpl, notes=notes + [f"cloned from SketchPlane {tpl}"])
    # remember the geometry for host_instance_on_wall
    el.face = {"tag": tag, "frame": fr, "wall_id": g.wall_id, "geom": g,
               "plane_ref": plane_ref}
    doc.new_elements.append(el)
    return el


# ---------------------------------------------------------------------------
# instance hosting
# ---------------------------------------------------------------------------
def host_instance_on_wall(doc: Document, symbol_id: int, wall,
                          distance_along_ft: float, elevation_ft: float = 4.0,
                          side: Union[str, int] = "interior", *,
                          sketchplane: Optional[NewElement] = None,
                          plane_ref: str = "geom",
                          level_id: Optional[int] = None,
                          template_instance_id: Optional[int] = None,
                          phase_id: Optional[int] = None) -> list:
    """Place ``symbol_id`` MOUNTED ON ``wall``'s face and return
    ``[sketchplane_el, instance_el]`` (both NewElements, in creation order).

    ``distance_along_ft``: distance from the wall's start point along its
    drawing direction to the family origin.  ``elevation_ft``: mounting
    height ABOVE the wall base (the level).  ``sketchplane``: reuse a plane
    created earlier (several panels share one plane in real files) — its
    face wins over ``side``/``plane_ref``.  ``level_id``: the level the
    element schedules to (default: the wall's base level).
    """
    if sketchplane is None:
        # anchor the plane at the mounting point so its origin is on the face
        g0 = wall_geometry(doc, wall)
        pt = g0.point_on_face(side, distance_along_ft,
                              g0.base_z + float(elevation_ft))
        sketchplane = add_sketchplane_on_wall(doc, wall, side, at_point_ft=pt,
                                              plane_ref=plane_ref)
    face = getattr(sketchplane, "face", None)
    if face is None:
        raise TypeError("sketchplane must be a NewElement from add_sketchplane_on_wall")
    g: WallFaceGeom = face["geom"]
    tag = face["tag"]
    lvl = level_id if level_id is not None else (g.level_id or _default_level(doc))
    if lvl is None:
        raise LookupError("no level: pass level_id explicitly")

    # mounting point ON the face, and the face frame anchored there
    z = g.base_z + float(elevation_ft)
    origin = g.point_on_face(tag, float(distance_along_ft), z)
    fr = face_frame(g, tag, origin)

    tinst = template_instance_id or _hosted_instance_template(doc, symbol_id)
    inst = doc.add_family_instance(symbol_id, lvl, position=origin, rotation=0.0,
                                   host_id=sketchplane.elem_id,
                                   template_instance_id=tinst,
                                   phase_id=phase_id)
    obj = inst.obj
    # --- face-hosted placement fields (verified on 742670 / 460372 / 460229)
    obj["m_workPlaneBased"] = True
    obj["m_hostId"] = sketchplane.elem_id
    obj["m_assocLevelId"] = -1                 # face-hosted: no level constraint...
    obj["m_scheduleOnlyLevelId"] = lvl          # ...but schedules to the level
    obj["m_workPlaneFlipped"] = False
    obj["m_flippedX"] = False
    obj["m_flippedY"] = False
    obj["m_hostParam"] = 0.0
    obj["m_elevation"] = 0.0
    obj["m_assocSketchPlaneId"] = -1
    ii = ((obj.get("m_pInstanceInfo") or {}).get("value")) or {}
    ii["m_symbolId"] = symbol_id
    ii["m_GRepId"] = 0
    ii["m_Trf"] = {"m_3x3": fr["m_3x3"], "m_or": fr["m_or"]}   # frame == the plane's

    # --- seq 103 GElement rep: same frame on the GInstance node -------------
    if inst.rep is not None:
        for node in inst.rep.get("m_subNodes") or []:
            nv = node.get("value") or {}
            info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                info["m_symbolId"] = symbol_id
                info["m_Trf"] = {"m_3x3": fr["m_3x3"], "m_or": fr["m_or"]}
        half = 1.5
        inst.rep["m_bBox"] = [[origin[0] - half, origin[1] - half, origin[2] - half],
                              [origin[0] + half, origin[1] + half, origin[2] + half]]
        inst.rep["m_tightbBox"] = inst.rep["m_bBox"]

    # --- header: keep the sketch plane in deletion; the WALL is a regen parent
    hdr_par = ((inst.header.get("m_parents") or {}).get("value")) or {}
    dele = set(hdr_par.get("m_deletion") or [])
    dele.update({sketchplane.elem_id, inst.elem_id, symbol_id, lvl})
    hdr_par["m_deletion"] = sorted(dele)
    ro = set(hdr_par.get("m_regenOnly") or [])
    if face.get("plane_ref") == "geom":
        ro.add(g.wall_id)                       # wall geometry drives the instance
    hdr_par["m_regenOnly"] = sorted(ro)
    ap = set(hdr_par.get("m_appearanceParents") or [])
    ap.add(symbol_id)
    hdr_par["m_appearanceParents"] = sorted(ap)
    if isinstance(inst.header.get("m_parents"), dict):
        inst.header["m_parents"]["value"] = hdr_par
    inst.header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1,
                              "value": {"m_minmax": [[origin[0] - 1.5, origin[1] - 1.5, origin[2] - 1.0],
                                                     [origin[0] + 1.5, origin[1] + 1.5, origin[2] + 2.5]]}}
    inst.kind = "hosted_instance"
    inst.notes.append(
        f"FACE-HOSTED on SketchPlane {sketchplane.elem_id} (wall {g.wall_id}, "
        f"face tag {tag}); frame Z = outward normal "
        f"{tuple(round(c, 4) for c in fr['n'])}; origin on face "
        f"({origin[0]:.3f}, {origin[1]:.3f}, {origin[2]:.3f}) ft = "
        f"{distance_along_ft:.2f} ft along, {elevation_ft:.2f} ft above wall base; "
        f"template instance {tinst}")
    return [sketchplane, inst]


def _default_level(doc: Document) -> Optional[int]:
    lv = doc.levels()
    if not lv:
        return None
    named = [l for l in lv if str(l.get("name") or "").strip().lower() == "level 1"]
    return (named or lv)[0]["id"]


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------
def _demo(project: str = "rmebasicsampleproject") -> dict:
    doc = Document.load(project)
    out = {"template": project, "checks": []}
    # 1. prove the frame formula on every real wall-face SketchPlane
    ok = bad = 0
    for spid in doc.ids_of_class("SketchPlane"):
        r = reconstruct_plane_trf(doc, spid)
        if r is None:
            continue
        pred = [[round(v, 6) for v in row] for row in r["predicted"]]
        got = [[round(v, 6) for v in row] for row in r["stored"]]
        if pred == got:
            ok += 1
        else:
            bad += 1
            out["checks"].append({"sketchplane": spid, "wall": r["wall"],
                                  "tag": r["tag"], "pred": pred, "stored": got})
    out["frame_formula"] = {"match": ok, "mismatch": bad}
    # 2. plan one hosted panel on an existing wall
    sp, inst = host_instance_on_wall(doc, symbol_id=619617, wall=573608,
                                     distance_along_ft=8.0, elevation_ft=4.0,
                                     side="exterior")
    out["planned"] = {
        "sketchplane": {"id": sp.elem_id, "notes": sp.notes},
        "instance": {"id": inst.elem_id, "trf": inst.obj["m_pInstanceInfo"]["value"]["m_Trf"],
                     "dangling_refs": doc.check_references(inst)},
        "sketchplane_dangling_refs": doc.check_references(sp),
    }
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(_demo(), indent=1, default=str))

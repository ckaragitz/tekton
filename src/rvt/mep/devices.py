"""devices.py — ELECTRICAL DEVICE & FIXTURE INSTANCES (MEP stream: devices).

Full CRUD over the point-hosted electrical categories an electrical
contractor touches: RECEPTACLES (``OST_ElectricalFixtures``), SWITCHES and
sensors (``OST_LightingDevices``), LIGHTING-FIXTURE INSTANCES
(``OST_LightingFixtures``), data / telephone / fire-alarm / security /
nurse-call devices, junction boxes and disconnects — i.e. every
``FamilyInstance`` category that a family ALREADY LOADED in the file can
place.  (Authoring the families themselves is the family stream.)

Everything here is derived from the Revit-MEP sample
(``samples/rmebasicsampleproject.rvt``) — see ``docs/writer/mep-devices.md``
for the decode evidence.  The three hosting flavours these categories use:

* **WALL face** (receptacles, switches, wall lights, wall boxes) — a
  vertical ``SketchPlane`` on the wall face; 416/424 receptacles and 63/63
  switches sit on a reference-less ``DummyPlaneRef`` work plane made
  COINCIDENT with the face, 8 receptacles on a ``GeomOnPlaneRef`` bound to
  the wall.  Both are written by :mod:`rvt.hosting`; this module adds the
  device semantics (mounting height, mark, room/space, native parents) and
  plane SHARING (several devices on one plane, as real files do).
* **CEILING** (recessed / pendant lights, sprinklers, ceiling sensors) — a
  HORIZONTAL, DOWN-FACING ``DummyPlaneRef`` work plane at the ceiling's
  underside elevation (410/410 lights, 48 planes); the fixture's frame keeps
  the plane's -Z normal and is rotated about it.  There is NO reference into
  a ``Ceiling`` element anywhere in the sample — the coincidence with the
  ceiling face is what makes the light "ceiling hosted".
* **FLOOR / LEVEL** (floor boxes, free-standing floor devices) — either a
  work plane referencing the LEVEL datum (``OnDatumPlaneRef``,
  ``m_datumPlaneId = level``; the pattern face-based families use when
  placed on a level), or a genuinely FREE instance (``m_hostId = -1``,
  level-based) for equipment-style families (transformer 624416).

CIRCUITS over MULTIPLE loads: :func:`add_multi_load_circuit` extends the
single-load :meth:`rvt.mutate.Document.add_circuit` to N loads on one
branch circuit off one panel, mirroring the real 4-load / 9-load specimens
(471829 / 469428): one member connector per load (``connType 1`` refs to the
load's supply connector), a FINAL base connector to the feeding panel's next
free 50000-series SLOT (``connType 4``), ``m_baseConnectorIdArray =
[{self, LAST}]``, and — CORRECTING ``KNOWLEDGE.md`` — ``m_pathNodes[0]
.m_elemId = the PANEL`` (base equipment), verified 171/171 circuits.

MODIFY / MOVE / RETYPE / DELETE of EXISTING devices are thin, device-aware
wrappers over :mod:`rvt.manipulate` (move within the host face, mounting
height, re-host to another face, mark, retype, detach-and-delete).

Public API (create — every call returns planned
:class:`rvt.mutate.NewElement` objects; write them with
``rvt.commit.commit_new_elements``)::

    from rvt.mutate import Document
    from rvt.mep import devices

    doc = Document.from_file("project.rvt")
    sp, recep = devices.add_wall_device(doc, 342654, wall=573608,
                                        distance_along_ft=6.0, elevation_ft=1.5)
    plane, light = devices.add_light_fixture(doc, 365612, (62.0, 110.0), ceiling_z_ft=20.51)
    fplane, fdev = devices.add_floor_device(doc, 342654, (64.0, 112.0), level_id=378117)
    circ = devices.add_multi_load_circuit(doc, panel, [r1, r2, r3, r4], rating=20)

Public API (edit an EXISTING device — returns rvt.manipulate plans; write
with ``rvt.manipulate.commit_plans`` / ``commit_session``)::

    devices.set_device_mark(doc, eid, "R-101")
    devices.set_mounting_height(doc, eid, 4.0)         # ft above its level
    devices.move_device_along_host(doc, eid, along_ft=2.0, up_ft=0.5)
    devices.retype_device(doc, eid, new_symbol_id)
    devices.delete_device(doc, eid)                    # detaches + deletes

``python -m rvt.mep.devices [file.rvt]`` prints the device inventory of a
project (loaded device symbols, hosting census, level table).
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from ..mutate import (CLASS_ELECTRICAL_SYSTEM, CLASS_SERIALIZED_DUMMY, Document,
                      NewElement, OST_ElectricalEquipment, OST_ElectricalFixtures,
                      OST_LightingFixtures)
from .. import hosting

__all__ = [
    # categories / discovery
    "DEVICE_CATEGORIES", "OST_LightingDevices", "OST_DataDevices",
    "OST_CommunicationDevices", "OST_FireAlarmDevices", "OST_SecurityDevices",
    "OST_NurseCallDevices", "OST_TelephoneDevices", "OST_MEPSpaces", "OST_Rooms",
    "device_symbols", "find_device_symbol", "device_census", "space_room_at",
    "level_at_or_below", "plane_frame",
    # create
    "add_wall_device", "add_device_on_plane", "add_ceiling_plane",
    "add_light_fixture", "add_level_datum_plane", "add_floor_device",
    "add_multi_load_circuit",
    # edit existing
    "device_placement", "set_device_mark", "set_mounting_height",
    "move_device_along_host", "rehost_device", "retype_device", "delete_device",
]

# ---------------------------------------------------------------------------
# categories (Autodesk BuiltInCategory ids — the file stores no name table)
# ---------------------------------------------------------------------------
OST_LightingDevices = -2008087        # switches, occupancy / daylight sensors
OST_DataDevices = -2008083
OST_CommunicationDevices = -2008081
OST_FireAlarmDevices = -2008085
OST_NurseCallDevices = -2008077
OST_SecurityDevices = -2008079
OST_TelephoneDevices = -2008075
OST_Rooms = -2000160
OST_MEPSpaces = -2003600                # MEP Spaces (RoomElem class objects)

#: every point-hosted device / fixture-INSTANCE category this stream owns
DEVICE_CATEGORIES: Dict[int, str] = {
    OST_ElectricalFixtures: "Electrical Fixtures (receptacles)",
    OST_LightingFixtures: "Lighting Fixtures",
    OST_LightingDevices: "Lighting Devices (switches / sensors)",
    OST_DataDevices: "Data Devices",
    OST_CommunicationDevices: "Communication Devices",
    OST_FireAlarmDevices: "Fire Alarm Devices",
    OST_NurseCallDevices: "Nurse Call Devices",
    OST_SecurityDevices: "Security Devices",
    OST_TelephoneDevices: "Telephone Devices",
    OST_ElectricalEquipment: "Electrical Equipment (panels / disconnects / xfmrs)",
}

#: internal Revit power / voltage units are (SI value) / 0.3048^2:
#: 120 V is stored as 1291.6692 and 720 VA as 7750.0155 (circuit 471829).
INTERNAL_PER_SI = 1.0 / (0.3048 ** 2)     # = 10.7639...

BIP_ALL_MODEL_MARK = -1001203

_UP = (0.0, 0.0, 1.0)
_DOWN = (0.0, 0.0, -1.0)


# ===========================================================================
# small vector helpers
# ===========================================================================
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _add(a, b, s=1.0):
    return tuple(float(a[i]) + s * float(b[i]) for i in range(3))


def _norm(v):
    n = math.sqrt(sum(float(c) * float(c) for c in v)) or 1.0
    return tuple(float(c) / n for c in v)


def _rows_from_columns(x, y, z):
    """Trf.m_3x3 is stored COLUMN-major: row i = (X.i, Y.i, Z.i)."""
    return [[float(x[0]), float(y[0]), float(z[0])],
            [float(x[1]), float(y[1]), float(z[1])],
            [float(x[2]), float(y[2]), float(z[2])]]


def _columns_from_rows(m3):
    m3 = m3 or [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    x = (m3[0][0], m3[1][0], m3[2][0])
    y = (m3[0][1], m3[1][1], m3[2][1])
    z = (m3[0][2], m3[1][2], m3[2][2])
    return x, y, z


def _rotate_in_plane(x, y, theta: float):
    """Rotate the in-plane axes (X, Y) about the plane normal by theta."""
    c, s = math.cos(theta), math.sin(theta)
    xr = tuple(c * x[i] + s * y[i] for i in range(3))
    yr = tuple(-s * x[i] + c * y[i] for i in range(3))
    return xr, yr


# ===========================================================================
# discovery: symbols, levels, spaces, existing planes
# ===========================================================================
def _names(doc: Document, symbol_id: int) -> Tuple[Optional[str], Optional[str]]:
    try:
        from .. import inventory
        return inventory.family_and_symbol_names(doc, symbol_id)
    except Exception:
        return (None, None)


def device_symbols(doc: Document, category: Optional[int] = None) -> List[dict]:
    """Every loaded device / fixture ``FamilySymbol`` (name, family, category,
    number of placed instances, dominant hosting flavour), so a caller can
    author against the project's OWN loaded content."""
    cats = {category} if category is not None else set(DEVICE_CATEGORIES)
    placed: Dict[int, int] = {}
    hosting_of: Dict[int, str] = {}
    for i in doc.ids_of_class("FamilyInstance"):
        v = doc.value(i)
        if not v:
            continue
        ii = ((v.get("m_pInstanceInfo") or {}).get("value")) or {}
        sid = ii.get("m_symbolId")
        placed[sid] = placed.get(sid, 0) + 1
        if sid not in hosting_of:
            hosting_of[sid] = _hosting_flavour(doc, v)
    out = []
    for sid in doc.ids_of_class("FamilySymbol"):
        cat = doc.category_of(sid)
        if cat not in cats:
            continue
        fam, name = _names(doc, sid)
        out.append({"symbol_id": sid, "family": fam, "name": name,
                    "category": cat, "category_label": DEVICE_CATEGORIES.get(cat),
                    "placed_instances": placed.get(sid, 0),
                    "hosting": hosting_of.get(sid, "unplaced")})
    out.sort(key=lambda r: (r["category"], -r["placed_instances"], r["symbol_id"]))
    return out


def find_device_symbol(doc: Document, text: str, category: Optional[int] = None,
                       *, family: Optional[str] = None) -> Optional[int]:
    """First loaded symbol whose 'Family :: Type' name contains ``text``
    (case-insensitive), most-placed first."""
    text = (text or "").lower()
    fam = (family or "").lower()
    best = None
    for row in device_symbols(doc, category):
        full = f"{row.get('family') or ''} :: {row.get('name') or ''}".lower()
        if text in full and (not fam or fam in (row.get("family") or "").lower()):
            if best is None or row["placed_instances"] > best["placed_instances"]:
                best = row
    return best["symbol_id"] if best else None


def _hosting_flavour(doc: Document, inst_value: dict) -> str:
    hid = inst_value.get("m_hostId")
    if not (isinstance(hid, int) and hid > 0):
        return "free"
    cls = doc.class_of(hid)
    if cls != "SketchPlane":
        return f"host:{cls}"
    sp = doc.value(hid) or {}
    pref = sp.get("m_oPlaneRef") or {}
    pc = pref.get("ptr_class")
    if pc == "GeomOnPlaneRef":
        gr = ((pref.get("value") or {}).get("m_geomRef") or {})
        return f"geom-plane->{doc.class_of(gr.get('m_elemId'))}"
    if pc == "OnDatumPlaneRef":
        return "datum-plane(level)"
    if pc == "DummyPlaneRef":
        _x, _y, z = _columns_from_rows(((sp.get("m_oTrf") or {}).get("value") or {}).get("m_3x3"))
        if abs(z[2]) > 0.5:
            return "ceiling-plane" if z[2] < 0 else "floor-plane"
        return "wall-plane(dummy)"
    return f"plane:{pc}"


def device_census(doc: Document) -> Dict[str, Any]:
    """Hosting census of every existing device instance by category — the
    quick way to see how THIS file mounts its devices."""
    from collections import Counter
    out: Dict[str, Any] = {}
    for i in doc.ids_of_class("FamilyInstance"):
        cat = doc.category_of(i)
        if cat not in DEVICE_CATEGORIES:
            continue
        v = doc.value(i)
        if not v:
            continue
        label = DEVICE_CATEGORIES[cat]
        out.setdefault(label, Counter())[_hosting_flavour(doc, v)] += 1
    return {k: dict(c) for k, c in out.items()}


def plane_frame(doc: Document, plane) -> dict:
    """The placement frame of a ``SketchPlane`` (existing id OR a plane
    :class:`NewElement`): columns ``X`` (in-plane +u), ``Y`` (in-plane +v),
    ``Z`` (the plane NORMAL a hosted family's +Z points along) and ``or``
    (the frame origin)."""
    if isinstance(plane, NewElement):
        sp, pid = plane.obj, plane.elem_id
    else:
        pid = int(plane)
        if (doc.class_of(pid) or "") != "SketchPlane":
            raise TypeError(f"element {pid} is a {doc.class_of(pid)!r}, not a SketchPlane")
        sp = doc.value(pid) or {}
    trf = ((sp.get("m_oTrf") or {}).get("value") or {})
    x, y, z = _columns_from_rows(trf.get("m_3x3"))
    org = tuple(float(c) for c in (trf.get("m_or") or [0.0, 0.0, 0.0]))
    return {"plane_id": pid, "X": _norm(x), "Y": _norm(y), "Z": _norm(z), "or": org,
            "ptr_class": ((sp.get("m_oPlaneRef") or {}).get("ptr_class"))}


def level_at_or_below(doc: Document, z_ft: float) -> Optional[int]:
    """The building level a point at elevation ``z_ft`` schedules to: the
    highest level whose elevation is <= z (default for face-hosted devices,
    whose ``m_scheduleOnlyLevelId`` is the level they belong to)."""
    lv = [l for l in doc.levels() if isinstance(l.get("elevation_ft"), (int, float))]
    if not lv:
        return None
    below = [l for l in lv if l["elevation_ft"] <= float(z_ft) + 1e-6]
    return (below[-1] if below else lv[0])["id"]


def _level_elevation(doc: Document, level_id: int) -> float:
    return float(doc._level_elevation(level_id))


# -- rooms & MEP spaces -------------------------------------------------------
def _room_index(doc: Document) -> List[dict]:
    """Cached [(id, category, bbox)] of every host-document RoomElem — rooms
    (``OST_Rooms``) AND MEP Spaces (``OST_MEPSpaces``), which are the SAME
    class (``RoomElem``) distinguished only by category."""
    cached = getattr(doc, "_devices_room_index", None)
    if cached is not None:
        return cached
    out = []
    for rid in doc.ids_of_class("RoomElem"):
        h = doc.decode(rid, 101)
        if h is None or not h.clean:
            continue
        cat = h.value.get("m_categroryId")
        mm = (((h.value.get("m_pBBox") or {}).get("value") or {}).get("m_minmax"))
        if not (isinstance(mm, list) and len(mm) == 2):
            continue
        out.append({"id": rid, "category": cat, "min": mm[0], "max": mm[1]})
    doc._devices_room_index = out
    return out


def space_room_at(doc: Document, point) -> Tuple[Optional[int], Optional[int]]:
    """(MEP space id, room id) whose bounding box contains ``point`` (ft;
    z optional).  Devices carry these in ``ElectricalFamInstDesignPropertyManager``
    (``m_idSpace`` / ``m_idRoom``) and list them among their header parents;
    Revit re-derives them on regeneration, so a miss (-1/None) is harmless."""
    px, py = float(point[0]), float(point[1])
    pz = float(point[2]) if len(point) > 2 else None
    best: Dict[int, Tuple[float, int]] = {}
    for r in _room_index(doc):
        (x0, y0, z0), (x1, y1, z1) = r["min"], r["max"]
        if not (x0 - 1e-6 <= px <= x1 + 1e-6 and y0 - 1e-6 <= py <= y1 + 1e-6):
            continue
        if pz is not None and not (z0 - 1.0 <= pz <= z1 + 1.0):
            continue
        area = (x1 - x0) * (y1 - y0)
        cat = r["category"]
        if cat not in best or area < best[cat][0]:
            best[cat] = (area, r["id"])
    space = best.get(OST_MEPSpaces, (None, None))[1]
    room = best.get(OST_Rooms, (None, None))[1]
    return space, room


# -- project-wide singletons the native device header names --------------------
def _singletons(doc: Document) -> dict:
    cached = getattr(doc, "_devices_singletons", None)
    if cached is not None:
        return cached
    out = {}
    for key, cls in (("units", "UnitsElem"), ("geo", "ActiveGeoLocationTrackingElement"),
                     ("mep_tracker", "MEPSystemTracker"), ("elec_setting", "ElectricalSetting"),
                     ("circuit_naming", "CircuitNamingTypeSetting")):
        ids = doc.ids_of_class(cls)
        out[key] = ids[0] if ids else None
    doc._devices_singletons = out
    return out


# ===========================================================================
# templates
# ===========================================================================
def _plane_flavour(doc: Document, plane_id: int) -> str:
    sp = doc.value(plane_id) or {}
    pref = sp.get("m_oPlaneRef") or {}
    pc = pref.get("ptr_class")
    if pc == "GeomOnPlaneRef":
        return "geom"
    if pc == "OnDatumPlaneRef":
        return "datum"
    if pc == "DummyPlaneRef":
        _x, _y, z = _columns_from_rows(((sp.get("m_oTrf") or {}).get("value") or {}).get("m_3x3"))
        if abs(z[2]) > 0.5:
            return "ceiling" if z[2] < 0 else "floorplane"
        return "dummy"
    return "other"


def _device_template(doc: Document, symbol_id: int, prefer: str = "dummy",
                     category: Optional[int] = None) -> Optional[int]:
    """A real placed instance to clone for ``symbol_id``: prefer one hosted on
    a plane of flavour ``prefer`` ('dummy' | 'geom' | 'ceiling' | 'datum' |
    'floorplane' | 'free'), else any hosted instance of the symbol, else the
    same category, else None (let ``add_family_instance`` decide)."""
    exact: List[Tuple[int, str]] = []
    same_cat: List[Tuple[int, str]] = []
    for i in doc.ids_of_class("FamilyInstance"):
        v = doc.value(i)
        if not v:
            continue
        ii = ((v.get("m_pInstanceInfo") or {}).get("value")) or {}
        sid, msid = ii.get("m_symbolId"), v.get("m_masterSymbolId")
        hid = v.get("m_hostId")
        if isinstance(hid, int) and hid > 0 and (doc.class_of(hid) == "SketchPlane"):
            flav = _plane_flavour(doc, hid)
        elif hid in (-1, None):
            flav = "free"
        else:
            flav = "other"
        if symbol_id in (sid, msid):
            exact.append((i, flav))
        elif category is not None and doc.category_of(i) == category:
            same_cat.append((i, flav))
    for pool in (exact, same_cat):
        for want in (prefer, None):
            for i, flav in pool:
                if want is None or flav == want:
                    return i
    return None


def _find_plane_template(doc: Document, flavour: str) -> int:
    """A real SketchPlane of the requested flavour to clone: 'ceiling'
    (horizontal down-facing DummyPlaneRef), 'floorplane' (up-facing dummy),
    'dummy' (vertical dummy), 'datum' (OnDatumPlaneRef), 'geom'."""
    best = None
    for spid in doc.ids_of_class("SketchPlane"):
        if _plane_flavour(doc, spid) == flavour:
            v = doc.value(spid) or {}
            if flavour == "datum" and v.get("m_userId", -1) not in (-1, None):
                if best is None:
                    best = spid           # sketch-user planes are 2nd choice
                continue
            return spid
    # graceful fallbacks between the dummy sub-flavours (all one class shape)
    if best is not None:
        return best
    if flavour in ("ceiling", "floorplane"):
        for spid in doc.ids_of_class("SketchPlane"):
            if _plane_flavour(doc, spid) in ("dummy", "ceiling", "floorplane"):
                return spid
    raise LookupError(f"{doc.project}: no {flavour!r} SketchPlane specimen to clone")


# ===========================================================================
# nativeisation of a created device (parents / space / mark)
# ===========================================================================
def _set_param_astring(obj: dict, param_id: int, value: str) -> bool:
    """Set an AString element parameter (e.g. the Mark).  Families whose
    donor never had one (switches, sensors) carry a NULL
    ``m_pParamValueSetAString``; the holder is created in that case (shape
    verified on receptacle 467291 / light 431705)."""
    if Document._set_param(obj, "m_pParamValueSetAString", param_id, str(value)):
        return True
    obj["m_pParamValueSetAString"] = {
        "ptr_class": "ParamValueSetAString", "pid": -1,
        "value": {"m_paramSet": [{"m_paramId": int(param_id), "m_value": str(value)}]}}
    return True


def _set_space_room(obj: dict, space: Optional[int], room: Optional[int]) -> None:
    dpm = obj.get("m_pDesignPropManager")
    v = dpm.get("value") if isinstance(dpm, dict) else None
    if isinstance(v, dict):
        v["m_idSpace"] = int(space) if space else -1
        v["m_idRoom"] = int(room) if room else -1


def _nativeize_device(doc: Document, inst: NewElement, symbol_id: int, *,
                      host_id: Optional[int], level_id: Optional[int],
                      point, mark: Optional[str] = None) -> dict:
    """Give a created device the header/object shape of a NATIVE device.

    Real receptacles / switches / lights (467291, 452792, 431705, 452442) all
    carry:  m_deletion = {phase, symbol, level, SPACE, ROOM, self, host
    plane (+ circuit/wires once wired)};  m_regenOnly = {UnitsElem, family,
    ActiveGeoLocationTrackingElement};  m_appearanceParents = {symbol,
    ActiveGeoLocationTrackingElement};  m_nonDetermRegenChildren = {SPACE};
    m_deferredParents = {MEPSystemTracker};  m_hasNonDetermRegenChildren=True;
    and ``ElectricalFamInstDesignPropertyManager.{m_idSpace,m_idRoom}``.
    """
    sing = _singletons(doc)
    space, room = space_room_at(doc, point)
    _set_space_room(inst.obj, space, room)
    if mark is not None:
        _set_param_astring(inst.obj, BIP_ALL_MODEL_MARK, mark)
    family = (doc.value(symbol_id) or {}).get("m_familyId")

    hdr_par = ((inst.header.get("m_parents") or {}).get("value")) or {}
    dele = set(hdr_par.get("m_deletion") or [])
    dele.update({inst.elem_id, symbol_id})
    for x in (host_id, level_id, space, room):
        if isinstance(x, int) and x > 0:
            dele.add(x)
    hdr_par["m_deletion"] = sorted(dele)
    ro = set(hdr_par.get("m_regenOnly") or [])
    for x in (family, sing.get("units"), sing.get("geo")):
        if isinstance(x, int) and x > 0:
            ro.add(x)
    hdr_par["m_regenOnly"] = sorted(ro)
    ap = set(hdr_par.get("m_appearanceParents") or [])
    ap.add(symbol_id)
    if sing.get("geo"):
        ap.add(sing["geo"])
    hdr_par["m_appearanceParents"] = sorted(ap)
    if space:
        hdr_par["m_nonDetermRegenChildren"] = [space]
        hdr_par["m_hasNonDetermRegenChildren"] = True
    if sing.get("mep_tracker"):
        hdr_par["m_deferredParents"] = [sing["mep_tracker"]]
    if isinstance(inst.header.get("m_parents"), dict):
        inst.header["m_parents"]["value"] = hdr_par
    return {"space": space, "room": room, "family": family}


# ===========================================================================
# generic: place a device ON A PLANE (existing plane id or planned plane)
# ===========================================================================
def _apply_frame(inst: NewElement, x, y, z, origin, symbol_id: int) -> None:
    """Write the placement frame everywhere a hosted instance caches it."""
    m3 = _rows_from_columns(x, y, z)
    org = [float(origin[0]), float(origin[1]), float(origin[2])]
    obj = inst.obj
    ii = ((obj.get("m_pInstanceInfo") or {}).get("value")) or {}
    ii["m_symbolId"] = symbol_id
    ii["m_GRepId"] = 0
    ii["m_Trf"] = {"m_3x3": m3, "m_or": list(org)}
    if inst.rep is not None:
        for node in inst.rep.get("m_subNodes") or []:
            nv = node.get("value") or {}
            info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                info["m_symbolId"] = symbol_id
                info["m_Trf"] = {"m_3x3": [list(r) for r in m3], "m_or": list(org)}
        h = 1.5
        inst.rep["m_bBox"] = [[org[0] - h, org[1] - h, org[2] - h],
                              [org[0] + h, org[1] + h, org[2] + h]]
        inst.rep["m_tightbBox"] = [list(r) for r in inst.rep["m_bBox"]]
    inst.header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1,
                              "value": {"m_minmax": [[org[0] - 1.5, org[1] - 1.5, org[2] - 1.0],
                                                     [org[0] + 1.5, org[1] + 1.5, org[2] + 2.5]]}}


def add_device_on_plane(doc: Document, symbol_id: int, plane, *,
                        uv: Optional[Tuple[float, float]] = None,
                        xyz=None, rotation: float = 0.0,
                        level_id: Optional[int] = None,
                        template_instance_id: Optional[int] = None,
                        mark: Optional[str] = None,
                        phase_id: Optional[int] = None,
                        kind: str = "hosted_device") -> NewElement:
    """Place ``symbol_id`` HOSTED on ``plane`` (an EXISTING SketchPlane id —
    the way real files pile many devices on one plane — or a plane planned in
    this run by any ``add_*_plane`` / ``rvt.hosting``).

    Position: ``uv=(u, v)`` in the plane frame (u along ``X``, v along
    ``Y``) OR a world ``xyz`` that is projected onto the plane.  ``rotation``
    turns the family about the plane normal.  ``level_id``: the level the
    device schedules to (default: the level at/below the mounting point; a
    ``face``-hosted device has ``m_assocLevelId = -1`` and
    ``m_scheduleOnlyLevelId = level`` — verified on every corpus device).
    """
    if not doc.exists(symbol_id):
        raise LookupError(f"symbol {symbol_id} not in {doc.project}")
    fr = plane_frame(doc, plane)
    pid = fr["plane_id"]
    org = fr["or"]
    if uv is not None:
        u, v = float(uv[0]), float(uv[1])
        point = _add(_add(org, fr["X"], u), fr["Y"], v)
    elif xyz is not None:
        p = (float(xyz[0]), float(xyz[1]),
             float(xyz[2]) if len(xyz) > 2 else org[2])
        d = tuple(p[i] - org[i] for i in range(3))
        u, v = _dot(d, fr["X"]), _dot(d, fr["Y"])
        point = _add(_add(org, fr["X"], u), fr["Y"], v)       # projected onto plane
    else:
        raise ValueError("pass uv= (plane coords) or xyz= (world point)")
    lvl = level_id if level_id is not None else level_at_or_below(doc, point[2])
    if lvl is None:
        raise LookupError("no level: pass level_id")
    prefer = _plane_flavour(doc, pid) if not isinstance(plane, NewElement) else \
        (getattr(plane, "plane_flavour", None) or "dummy")
    if prefer == "floorplane":
        prefer = "datum"
    tinst = template_instance_id or _device_template(
        doc, symbol_id, prefer=prefer, category=doc.category_of(symbol_id))
    inst = doc.add_family_instance(symbol_id, lvl, position=point, rotation=0.0,
                                   host_id=pid, template_instance_id=tinst,
                                   phase_id=phase_id)
    obj = inst.obj
    # face-hosted placement fields (verified 742670 / 460372 / 431705 / 579920)
    obj["m_workPlaneBased"] = True
    obj["m_hostId"] = pid
    obj["m_assocLevelId"] = -1
    obj["m_scheduleOnlyLevelId"] = lvl
    obj["m_workPlaneFlipped"] = False
    obj["m_flippedX"] = False
    obj["m_flippedY"] = False
    obj["m_hostParam"] = 0.0
    obj["m_elevation"] = 0.0
    obj["m_assocSketchPlaneId"] = -1
    x, y = _rotate_in_plane(fr["X"], fr["Y"], float(rotation)) if rotation else (fr["X"], fr["Y"])
    _apply_frame(inst, x, y, fr["Z"], point, symbol_id)
    extra = _nativeize_device(doc, inst, symbol_id, host_id=pid, level_id=lvl,
                              point=point, mark=mark)
    inst.kind = kind
    inst.notes.append(
        f"HOSTED on SketchPlane {pid} ({fr.get('ptr_class') or 'planned'}); frame "
        f"Z=normal {tuple(round(c, 4) for c in fr['Z'])}, origin "
        f"({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f}) ft = uv "
        f"({u:.3f}, {v:.3f}); schedules to level {lvl}; space {extra['space']} "
        f"room {extra['room']}; template instance {tinst}")
    return inst


# ===========================================================================
# WALL devices — receptacles, switches, wall boxes
# ===========================================================================
def add_wall_device(doc: Document, symbol_id: int, wall,
                    distance_along_ft: float, elevation_ft: float = 1.5,
                    side: Union[str, int, None] = None, *,
                    facing_point=None, plane_ref: str = "dummy",
                    sketchplane: Optional[NewElement] = None,
                    level_id: Optional[int] = None,
                    template_instance_id: Optional[int] = None,
                    mark: Optional[str] = None,
                    phase_id: Optional[int] = None) -> List[NewElement]:
    """Mount a device (receptacle / switch / wall box / wall light) on the FACE
    of ``wall`` (an existing wall id OR a wall planned this run), at
    ``distance_along_ft`` from the wall start along its drawing direction and
    ``elevation_ft`` ABOVE the wall's base level (the mounting height).

    Face selection: ``side='interior'|'exterior'|5|6``, or (preferred, since
    interior/exterior are drawing-direction conventions) ``facing_point`` = a
    point INSIDE the room the device serves.  ``plane_ref='dummy'`` (default,
    416/424 receptacles + 63/63 switches in the sample) writes a reference-less
    work plane COINCIDENT with the face; ``'geom'`` writes a true
    ``GeomOnPlaneRef`` face reference into the wall.  Pass ``sketchplane=`` (a
    plane returned by an earlier call) so several devices SHARE one plane.
    Returns ``[sketchplane, instance]`` (or ``[instance]`` when the plane
    was supplied).
    """
    if side is None:
        if facing_point is None:
            side = "interior"
        else:
            side = hosting.side_facing_point(doc, wall, facing_point)
    tinst = template_instance_id or _device_template(
        doc, symbol_id, prefer=plane_ref, category=doc.category_of(symbol_id))
    made = hosting.host_instance_on_wall(
        doc, symbol_id=symbol_id, wall=wall,
        distance_along_ft=distance_along_ft, elevation_ft=elevation_ft,
        side=side, sketchplane=sketchplane, plane_ref=plane_ref,
        level_id=level_id, template_instance_id=tinst, phase_id=phase_id)
    sp, inst = made[0], made[1]
    lvl = inst.obj.get("m_scheduleOnlyLevelId")
    ii = ((inst.obj.get("m_pInstanceInfo") or {}).get("value")) or {}
    org = (ii.get("m_Trf") or {}).get("m_or") or [0.0, 0.0, 0.0]
    extra = _nativeize_device(doc, inst, symbol_id, host_id=sp.elem_id, level_id=lvl,
                              point=org, mark=mark)
    inst.kind = "wall_device"
    inst.notes.append(f"device semantics: space {extra['space']} room {extra['room']}"
                      f"{' mark ' + repr(mark) if mark else ''}")
    return [sp, inst] if sketchplane is None else [inst]


# ===========================================================================
# CEILING lighting fixtures (and any ceiling device)
# ===========================================================================
def add_ceiling_plane(doc: Document, origin, *, facing: str = "down",
                      template_id: Optional[int] = None) -> NewElement:
    """A horizontal work plane at ceiling elevation ``origin[2]`` (ft),
    facing DOWN by default (``facing='up'`` for a floor / roof-top plane).

    Reproduces the sample's ceiling planes byte-for-byte in shape: class
    ``SketchPlane`` with a ``DummyPlaneRef -> Plane{origin, xVec=(1,0,0),
    yVec=(0,-1,0)}`` (normal xVec x yVec = -Z), ``m_oTrf`` columns X=(1,0,0),
    Y=(0,-1,0), Z=(0,0,-1), NO reference to any ceiling element, header parents
    ``m_deletion = [self]``.  410/410 lighting fixtures in the sample stand on
    exactly such planes (48 shared planes).
    """
    down = (str(facing).lower() != "up")
    x = (1.0, 0.0, 0.0)
    y = (0.0, -1.0, 0.0) if down else (0.0, 1.0, 0.0)
    z = _DOWN if down else _UP
    org = [float(origin[0]), float(origin[1]), float(origin[2])]
    tpl = template_id or _find_plane_template(doc, "ceiling" if down else "floorplane")
    tval = doc.value(tpl)
    if not tval:
        raise LookupError(f"template SketchPlane {tpl} did not decode")
    eid = doc.next_id()
    obj = copy.deepcopy(tval)
    obj.update({"m_id": eid, "m_famId": -1, "m_designOptionId": -1,
                "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
                "m_locked": False, "m_userId": -1, "m_flipZ": False,
                "m_assocLevelId": -1})
    obj["m_oTrf"] = {"ptr_class": "Trf", "pid": -1,
                     "value": {"m_3x3": _rows_from_columns(x, y, z), "m_or": list(org)}}
    pref = obj.get("m_oPlaneRef") or {}
    if pref.get("ptr_class") != "DummyPlaneRef":
        # rebuild a DummyPlaneRef from scratch (any dummy plane has this shape)
        obj["m_oPlaneRef"] = pref = {"ptr_class": "DummyPlaneRef", "pid": -1, "value": {}}
    pv = pref.setdefault("value", {}) or {}
    gr = pv.get("m_geomRef")
    if not isinstance(gr, dict):
        gr = {}
    gr.update({"m_intermediateTags": [], "m_oNextRef": None, "m_elemId": -1,
               "m_ownerDBViewId": -1, "m_foreignElemIdRef": {"m_id64": -1},
               "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
               "m_flags": 0, "m_isLazyRef": False})
    pv["m_geomRef"] = gr
    plane = (pv.get("m_pPlane") or {}).get("value")
    if not isinstance(plane, dict):
        plane = {}
        pv["m_pPlane"] = {"ptr_class": "Plane", "pid": -1, "value": plane}
    plane["m_orientFlag"] = True
    plane["m_origin"] = list(org)
    plane["m_xVec"] = [float(c) for c in x]
    plane["m_yVec"] = [float(c) for c in y]           # normal = xVec x yVec = Z
    if not plane.get("m_Envelope"):
        plane["m_Envelope"] = {"m_corners": [[1.0, 1.0], [0.0, 0.0]]}
    pref["value"] = pv

    header = copy.deepcopy(doc.value(tpl, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = -1
    header["m_familyId"] = -1
    header["m_miscId"] = -1
    par = ((header.get("m_parents") or {}).get("value")) or {}
    par.update({"m_deletion": [eid], "m_regenOnly": [], "m_regenWildcards": [],
                "m_nonDetermRegenChildren": [], "m_dependencyParents": [],
                "m_appearanceParents": [], "m_deferredParents": [],
                "m_deferredPropagationParents": [], "m_computedParametersParents": [],
                "m_hasNonDetermRegenChildren": False})
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = par
    header["m_pBBox"] = None
    rec = doc.record(tpl)
    class_id = rec.class_id if rec is not None else hosting.CLASS_SKETCHPLANE
    el = NewElement(eid, "sketchplane", "SketchPlane", class_id, header, obj,
                    None, doc._new_elemrec(eid), tpl,
                    notes=[f"{'ceiling (down-facing)' if down else 'floor/roof (up-facing)'} "
                           f"DummyPlaneRef work plane at z {org[2]:.4f} ft, origin "
                           f"({org[0]:.3f}, {org[1]:.3f}); no reference into any element "
                           f"(the corpus pattern for ceiling hosting); cloned from "
                           f"SketchPlane {tpl}"])
    el.plane_flavour = "ceiling" if down else "floorplane"
    doc.new_elements.append(el)
    return el


def add_light_fixture(doc: Document, symbol_id: int, position, *,
                      ceiling_z_ft: Optional[float] = None,
                      ceiling_plane=None, rotation: float = 0.0,
                      level_id: Optional[int] = None,
                      template_instance_id: Optional[int] = None,
                      mark: Optional[str] = None,
                      phase_id: Optional[int] = None) -> List[NewElement]:
    """Place a ceiling lighting fixture (recessed troffer / downlight /
    pendant / ceiling sensor) at world ``position`` (x, y[, z]) hanging from
    the ceiling plane at ``ceiling_z_ft`` (= the ceiling's underside; pass
    ``ceiling_plane`` — an existing horizontal SketchPlane id or a plane made
    by :func:`add_ceiling_plane` — to SHARE one plane across a whole ceiling,
    the way the sample's 48 ceiling planes each carry 22-76 fixtures).

    The fixture's frame is the ceiling plane's frame rotated ``rotation``
    radians about the plane normal: Z = (0,0,-1) (down), X/Y in the ceiling
    plane; ``m_or`` = the mounting point ON the ceiling; ``m_assocLevelId
    = -1``, ``m_scheduleOnlyLevelId`` = the level the ceiling belongs to
    (default: the level at/below the fixture).  Returns ``[plane, fixture]``
    (or ``[fixture]`` for a supplied plane).
    """
    made: List[NewElement] = []
    if ceiling_plane is None:
        if ceiling_z_ft is None and len(position) < 3:
            raise ValueError("give ceiling_z_ft (or a 3-D position) for a new ceiling plane")
        zc = float(ceiling_z_ft) if ceiling_z_ft is not None else float(position[2])
        ceiling_plane = add_ceiling_plane(doc, (position[0], position[1], zc))
        made.append(ceiling_plane)
    fr = plane_frame(doc, ceiling_plane)
    zc = fr["or"][2]
    pt = (float(position[0]), float(position[1]), zc)
    inst = add_device_on_plane(doc, symbol_id, ceiling_plane, xyz=pt, rotation=rotation,
                               level_id=level_id, template_instance_id=template_instance_id,
                               mark=mark, phase_id=phase_id, kind="ceiling_fixture")
    inst.notes.append(f"CEILING fixture: normal -Z (down), mounting point on ceiling z "
                      f"{zc:.4f} ft, in-plane rotation {rotation:.4f} rad")
    made.append(inst)
    return made


# ===========================================================================
# FLOOR / LEVEL devices — floor boxes, free-standing floor devices
# ===========================================================================
def add_level_datum_plane(doc: Document, level_id: int, at_xy=(0.0, 0.0), *,
                          template_id: Optional[int] = None) -> NewElement:
    """A work plane bound to a LEVEL datum (``SketchPlane`` with
    ``OnDatumPlaneRef{m_datumPlaneId = level, m_vecInPlane = origin}``), the
    plane face-based families sit on when placed "on Level N" (specimen
    573289 / instances 579920-579923).  Up-facing identity frame at the
    level elevation."""
    if (doc.class_of(level_id) or "") != "Level":
        raise TypeError(f"{level_id} is a {doc.class_of(level_id)!r}, not a Level")
    z = _level_elevation(doc, level_id)
    tpl = template_id or _find_plane_template(doc, "datum")
    tval = doc.value(tpl)
    if not tval:
        raise LookupError(f"template SketchPlane {tpl} did not decode")
    eid = doc.next_id()
    org = [float(at_xy[0]), float(at_xy[1]), float(z)]
    obj = copy.deepcopy(tval)
    obj.update({"m_id": eid, "m_famId": -1, "m_designOptionId": -1,
                "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
                "m_locked": False, "m_userId": -1, "m_flipZ": False,
                "m_assocLevelId": -1})
    obj["m_oTrf"] = {"ptr_class": "Trf", "pid": -1,
                     "value": {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                               "m_or": list(org)}}
    pref = obj.get("m_oPlaneRef") or {}
    if pref.get("ptr_class") != "OnDatumPlaneRef":
        obj["m_oPlaneRef"] = pref = {"ptr_class": "OnDatumPlaneRef", "pid": -1, "value": {}}
    pv = pref.setdefault("value", {}) or {}
    gr = pv.get("m_geomRef")
    if not isinstance(gr, dict):
        gr = {}
    gr.update({"m_intermediateTags": [], "m_oNextRef": None, "m_elemId": -1,
               "m_ownerDBViewId": -1, "m_foreignElemIdRef": {"m_id64": -1},
               "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
               "m_flags": 0, "m_isLazyRef": False})
    pv["m_geomRef"] = gr
    pv["m_vecInPlane"] = [org[0], org[1], 0.0]          # plane origin (in-datum)
    pv["m_rotation"] = 0.0
    pv["m_datumPlaneId"] = level_id                      # THE LEVEL is the datum
    pv["m_mirror"] = False
    pref["value"] = pv
    header = copy.deepcopy(doc.value(tpl, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = -1
    header["m_familyId"] = -1
    header["m_miscId"] = -1
    par = ((header.get("m_parents") or {}).get("value")) or {}
    par.update({"m_deletion": sorted({eid, level_id}), "m_regenOnly": [],
                "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
                "m_dependencyParents": [], "m_appearanceParents": [],
                "m_deferredParents": [], "m_deferredPropagationParents": [],
                "m_computedParametersParents": [], "m_hasNonDetermRegenChildren": False})
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = par
    header["m_pBBox"] = None
    rec = doc.record(tpl)
    class_id = rec.class_id if rec is not None else hosting.CLASS_SKETCHPLANE
    el = NewElement(eid, "sketchplane", "SketchPlane", class_id, header, obj,
                    None, doc._new_elemrec(eid), tpl,
                    notes=[f"LEVEL work plane: OnDatumPlaneRef -> level {level_id} "
                           f"(z {z:.4f} ft) at ({org[0]:.3f}, {org[1]:.3f}); header "
                           f"deletion = [level, self]; cloned from SketchPlane {tpl}"])
    el.plane_flavour = "datum"
    doc.new_elements.append(el)
    return el


def add_floor_device(doc: Document, symbol_id: int, position_xy, level_id: int, *,
                     hosting_mode: str = "datum", rotation: float = 0.0,
                     datum_plane=None,
                     template_instance_id: Optional[int] = None,
                     mark: Optional[str] = None,
                     phase_id: Optional[int] = None) -> List[NewElement]:
    """A floor / free-standing device on ``level_id`` at ``position_xy``.

    ``hosting_mode='datum'`` (default — the pattern face-based device
    families use when placed on a level): the device is work-plane-based on a
    ``SketchPlane`` referencing the LEVEL datum (specimen: 4 instances on
    plane 573289 -> Level 1); pass ``datum_plane`` to share one.
    ``hosting_mode='free'``: a genuinely FREE, level-based instance
    (``m_hostId=-1``, ``m_workPlaneBased=False``) — the pattern for
    equipment-style families (transformer 624416, switchboard 630241).
    Returns ``[plane, device]`` / ``[device]``.
    """
    z = _level_elevation(doc, level_id)
    if hosting_mode == "free":
        tinst = template_instance_id or _device_template(
            doc, symbol_id, prefer="free", category=doc.category_of(symbol_id))
        inst = doc.add_family_instance(symbol_id, level_id,
                                       position=(float(position_xy[0]), float(position_xy[1]), z),
                                       rotation=float(rotation), template_instance_id=tinst,
                                       phase_id=phase_id)
        extra = _nativeize_device(doc, inst, symbol_id, host_id=None, level_id=level_id,
                                  point=(position_xy[0], position_xy[1], z), mark=mark)
        inst.kind = "floor_device"
        inst.notes.append(f"FREE level-based floor device on level {level_id} "
                          f"(hostId -1); space {extra['space']} room {extra['room']}")
        return [inst]
    if hosting_mode != "datum":
        raise ValueError("hosting_mode must be 'datum' or 'free'")
    made: List[NewElement] = []
    if datum_plane is None:
        datum_plane = add_level_datum_plane(doc, level_id, at_xy=position_xy)
        made.append(datum_plane)
    inst = add_device_on_plane(doc, symbol_id, datum_plane,
                               xyz=(float(position_xy[0]), float(position_xy[1]), z),
                               rotation=rotation, level_id=level_id,
                               template_instance_id=template_instance_id, mark=mark,
                               phase_id=phase_id, kind="floor_device")
    inst.notes.append(f"FLOOR device on the level-{level_id} datum plane (z {z:.4f} ft)")
    made.append(inst)
    return made


# ===========================================================================
# CIRCUITS over MULTIPLE loads
# ===========================================================================
def _template_multi_circuit(doc: Document, min_conns: int) -> int:
    """Smallest real ``RbsElectricalSystem`` with >= ``min_conns`` own
    connectors (prefer an exact match: rme has six 5-connector circuits =
    4 loads + panel, and 19 x 10-connector = 9 loads + panel)."""
    exact, bigger = None, None
    for cid in doc.ids_of_class("RbsElectricalSystem"):
        v = doc.value(cid) or {}
        n = len((Document._conn_manager(v) or {}).get("m_connPtrArray") or [])
        if n == min_conns and exact is None:
            exact = cid
        elif n > min_conns and (bigger is None or n < bigger[1]):
            bigger = (cid, n)
    if exact is not None:
        return exact
    if bigger is not None:
        return bigger[0]
    raise LookupError(f"{doc.project}: no circuit with >= {min_conns} connectors to clone")


def _first_supply_index(doc: Document, load_obj: dict) -> int:
    idx = Document._connector_indexes(load_obj)
    low = sorted(i for i in idx if isinstance(i, int) and 0 < i < 1000)
    return low[0] if low else (idx[0] if idx else 1)


def add_multi_load_circuit(doc: Document, panel: NewElement, loads: Sequence[NewElement], *,
                           number: str = "1", description: Optional[str] = None,
                           rating: float = 20.0, poles: int = 1,
                           voltage_v: Optional[float] = 120.0,
                           apparent_load_va_per_load: Optional[float] = 180.0,
                           load_classification: Optional[str] = "Receptacles",
                           panel_conn_index: Optional[int] = None,
                           template_id: Optional[int] = None) -> NewElement:
    """One BRANCH CIRCUIT (``RbsElectricalSystem``) putting several NEW
    ``loads`` on the NEW ``panel`` (all created in this same commit — the
    connector back-links are wired here, pre-serialisation).

    The record shape is the real N-load specimen (471829: 4 receptacles;
    469428: 9 receptacles), corrected against 187 corpus circuits:

    * one own connector per load: ``conn[i].m_arrRefs = [{load_i, load's
      supply connector (its lowest small index, ~1), connType 1}]``;
    * a FINAL connector for the base equipment: ``conn[LAST].m_arrRefs =
      [{panel, next free 50000-series SLOT, connType 4}]`` — a panel's
      50000-series connectors are per-circuit slots, one circuit each;
    * ``m_baseConnectorIdArray = [{self, LAST index, connType 4}]``;
    * BACK-LINKS: each load's supply connector ``m_arrRefs -> {circuit, i,
      connType 4}``; the panel's slot connector ``-> {circuit, LAST, 4}``;
    * ``m_pathNodes[0].m_elemId = the PANEL`` (verified 171/171 circuits
      with path nodes — NOT the first load as older notes said); later
      nodes are virtual, translated with the panel;
    * header parents: ``m_deletion = {loads, panel, self, cable type/size,
      load classification}``, ``m_appearanceParents = {loads, panel}``,
      ``m_regenOnly = {load symbol, ElectricalSetting, CircuitNamingTypeSetting}``.

    ``voltage_v`` / ``apparent_load_va_per_load`` are SI values converted
    to Revit internal units (x 1/0.3048^2 = 10.7639): 120 V -> 1291.669,
    720 VA -> 7750.0155 (both byte-exact against circuit 471829).
    """
    n = len(loads)
    if n < 1:
        raise ValueError("a circuit needs at least one load")
    if not isinstance(panel, NewElement) or any(not isinstance(l, NewElement) for l in loads):
        raise TypeError("panel and loads must be NewElements created in this same "
                        "run (circuiting EXISTING elements needs in-place record "
                        "edits — phase 2)")
    tpl = template_id or _template_multi_circuit(doc, n + 1)
    sid = doc.next_id()
    tval = doc.value(tpl)
    obj = copy.deepcopy(tval)
    doc._remap_ids(obj, {tval.get("m_id"): sid})
    obj["m_id"] = sid

    # -- panel slot (never shared; track slots used per panel in this session)
    used = getattr(doc, "_panel_slots_used", None)
    if used is None:
        used = doc._panel_slots_used = {}
    taken = used.setdefault(panel.elem_id, set())
    pidx = Document._connector_indexes(panel.obj)
    if panel_conn_index is None:
        free = sorted(i for i in pidx if isinstance(i, int) and i >= 50000 and i not in taken)
        if free:
            panel_conn_index = free[0]
        else:                                       # extend past the highest slot
            hi = [i for i in pidx if isinstance(i, int) and i >= 50000]
            panel_conn_index = (max(hi) + 1) if hi else 50000
    taken.add(panel_conn_index)

    # -- circuit's own connectors: n load connectors + LAST = panel ---------
    mgr = Document._conn_manager(obj)
    if mgr is None:
        raise LookupError(f"circuit template {tpl} has no connector manager")
    conns = list(mgr.get("m_connPtrArray") or [])
    if len(conns) < n + 1:
        raise LookupError(f"circuit template {tpl} has only {len(conns)} connectors "
                          f"(< {n + 1} needed)")
    # keep the first n and the LAST (each Connector object keeps its own
    # archive pid, so truncating never duplicates a pid)
    keep = conns[:n] + [conns[-1]]
    mgr["m_connPtrArray"] = keep
    mgr["m_setDeletedConnectors"] = []
    base_index = None
    load_link_index: List[Tuple[int, int]] = []
    first = (keep[0].get("value") or {}).get("m_nIndex")
    start = int(first) if isinstance(first, int) and 0 <= first < 1000 else 0
    for k, c in enumerate(keep):
        cv = c.get("value") or {}
        idx_k = start + k
        cv["m_nIndex"] = idx_k
        if k < n:
            load = loads[k]
            lconn = _first_supply_index(doc, load.obj)
            cv["m_arrRefs"] = [{"m_id": load.elem_id, "m_nIndex": lconn,
                                "m_connType": 1}]
            load_link_index.append((idx_k, lconn))
        else:
            base_index = idx_k
            cv["m_arrRefs"] = [{"m_id": panel.elem_id, "m_nIndex": panel_conn_index,
                                "m_connType": 4}]
    obj["m_baseConnectorIdArray"] = [{"m_id": sid, "m_nIndex": base_index, "m_connType": 4}]

    # -- path nodes: node 0 = the panel; virtual nodes keep the template's
    #    relative shape, re-anchored at the panel origin -----------------------
    def _origin(o):
        ii = ((o.get("m_pInstanceInfo") or {}).get("value")) or {}
        t = (ii.get("m_Trf") or {}).get("m_or") or o.get("m_instOrigin")
        return [float(c) for c in t] if t else [0.0, 0.0, 0.0]
    ppos = _origin(panel.obj)
    nodes = obj.get("m_pathNodes") or []
    if nodes:
        anchor = list(nodes[0].get("m_position") or ppos)
        delta = [ppos[i] - anchor[i] for i in range(3)]
        for k, nd in enumerate(nodes):
            p = nd.get("m_position") or anchor
            nd["m_position"] = [p[i] + delta[i] for i in range(3)]
            if k == 0:
                nd["m_elemId"] = panel.elem_id
                nd["m_isVirtualNode"] = False
            else:
                nd["m_elemId"] = -1
                nd["m_isVirtualNode"] = True

    # -- electrical values ------------------------------------------------------
    obj["m_number"] = str(number)
    if description is not None:
        obj["m_strDescription"] = str(description)
    obj["m_dRating"] = float(rating)
    obj["m_nPoles"] = int(poles)
    if voltage_v is not None:
        obj["m_dVoltage"] = float(voltage_v) * INTERNAL_PER_SI
    if apparent_load_va_per_load is not None:
        tot = float(apparent_load_va_per_load) * n * INTERNAL_PER_SI
        obj["m_dApparentLoad"] = tot
        obj["m_dTrueLoad"] = tot
    if load_classification is not None:
        obj["m_strLoadClassifications"] = str(load_classification)
    obj["m_numberOfElements"] = n
    obj["m_numberOfElementsInNetwork"] = n

    # -- header parents ---------------------------------------------------------
    header = copy.deepcopy(doc.value(tpl, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    par = ((header.get("m_parents") or {}).get("value")) or {}
    deletion = {sid, panel.elem_id} | {l.elem_id for l in loads}
    for key in ("m_cableType", "m_cableSizeElementId"):
        v = obj.get(key)
        if isinstance(v, int) and v > 0 and doc.exists(v):
            deletion.add(v)
    # the load classification element named by m_strLoadClassifications
    lc_name = str(obj.get("m_strLoadClassifications") or "").strip().lower()
    for lcid in doc.ids_of_class("ElectricalLoadClassification"):
        try:
            from .. import inventory
            nm = (inventory.element_name(doc, lcid) or "").strip().lower()
        except Exception:
            nm = ""
        if nm and nm == lc_name:
            deletion.add(lcid)
            break
    regen = set()
    sing = _singletons(doc)
    for x in (sing.get("elec_setting"), sing.get("circuit_naming")):
        if isinstance(x, int) and x > 0:
            regen.add(x)
    for l in loads:
        ii = ((l.obj.get("m_pInstanceInfo") or {}).get("value")) or {}
        s = ii.get("m_symbolId")
        if isinstance(s, int) and s > 0:
            regen.add(s)
    par.update({
        "m_deletion": sorted(deletion),
        "m_regenOnly": sorted(regen), "m_regenWildcards": [],
        "m_nonDetermRegenChildren": [], "m_dependencyParents": [],
        "m_appearanceParents": sorted({panel.elem_id} | {l.elem_id for l in loads}),
        "m_deferredParents": ([sing["mep_tracker"]] if sing.get("mep_tracker") else []),
        "m_deferredPropagationParents": [], "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": True,
    })
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = par

    # -- back-links on the loads and the panel (same-run objects) -------------
    linked = []
    for (idx_k, lconn), load in zip(load_link_index, loads):
        ok = Document._link_connector(load.obj, lconn, sid, idx_k, conn_type=4)
        linked.append((load.elem_id, lconn, ok))
    okp = Document._link_connector(panel.obj, panel_conn_index, sid, base_index,
                                   conn_type=4)

    notes = [
        f"cloned from circuit {tpl} ({len(conns)} connectors -> {n + 1}); "
        f"{n} load connector(s) idx {start}..{start + n - 1} + base idx {base_index} "
        f"-> panel {panel.elem_id} slot {panel_conn_index} "
        f"({'linked' if okp else 'NO panel connector back-link'}); "
        f"loads " + ", ".join(f"{lid}:{lc}{'' if ok else '!'}" for lid, lc, ok in linked),
        f"path node 0 = panel {panel.elem_id} (real-model rule); "
        f"{voltage_v} V / {rating} A / {poles} P, "
        f"{n} x {apparent_load_va_per_load} VA ({load_classification})",
    ]
    el = NewElement(sid, "circuit", "RbsElectricalSystem", CLASS_ELECTRICAL_SYSTEM,
                    header, obj, None, doc._new_elemrec(sid), tpl, notes=notes)
    doc.new_elements.append(el)
    return el


# ===========================================================================
# EDIT EXISTING devices (wrappers over rvt.manipulate)
# ===========================================================================
def device_placement(doc: Document, eid: int) -> dict:
    """A device's placement: world origin, its host plane's frame, and the
    (u, v) coordinates of the origin IN that plane (u = along the wall /
    ceiling X, v = up / plane Y) — the coordinates a device move works in."""
    from .. import manipulate as M
    pl = M.instance_placement(doc, eid)
    out = dict(pl)
    hid = pl.get("m_hostId")
    if isinstance(hid, int) and hid > 0 and doc.class_of(hid) == "SketchPlane":
        fr = plane_frame(doc, hid)
        d = tuple(float(pl["m_or"][i]) - fr["or"][i] for i in range(3))
        out["host_plane"] = hid
        out["host_flavour"] = _plane_flavour(doc, hid)
        out["frame"] = fr
        out["uv"] = (_dot(d, fr["X"]), _dot(d, fr["Y"]))
        out["off_plane"] = _dot(d, fr["Z"])
    lvl = (doc.value(eid) or {}).get("m_scheduleOnlyLevelId")
    if isinstance(lvl, int) and lvl > 0:
        out["level_id"] = lvl
        out["height_above_level_ft"] = float(pl["m_or"][2]) - _level_elevation(doc, lvl)
    return out


def set_device_mark(doc: Document, eid: int, mark: str):
    """Set an existing device's 'Mark' (``BIP_ALL_MODEL_MARK``)."""
    from .. import manipulate as M
    return M.set_mark(doc, eid, str(mark))


def move_device_along_host(doc: Document, eid: int, along_ft: float = 0.0,
                           up_ft: float = 0.0):
    """Slide a face-hosted device WITHIN its host plane: ``along_ft`` along
    the plane X (= along the wall for a wall device / +X of the ceiling
    plane for a light), ``up_ft`` along the plane Y (= UP for a wall device
    = a mounting-height change).  The device never leaves its face."""
    from .. import manipulate as M
    pl = device_placement(doc, eid)
    fr = pl.get("frame")
    if fr is None:
        raise TypeError(f"element {eid} is not hosted on a SketchPlane "
                        f"(host {pl.get('m_hostId')})")
    delta = _add(_add((0.0, 0.0, 0.0), fr["X"], float(along_ft)), fr["Y"], float(up_ft))
    plan = M.move_instance(doc, eid, list(delta), None, delta=True)
    plan.notes.append(f"moved within host plane {pl['host_plane']}: "
                      f"{along_ft:+.3f} ft along X, {up_ft:+.3f} ft along Y")
    return plan


def set_mounting_height(doc: Document, eid: int, height_above_level_ft: float):
    """Set a device's mounting height ABOVE the level it schedules to (a pure
    +Z translation of its placement, i.e. an ``up`` move on a wall face)."""
    from .. import manipulate as M
    pl = device_placement(doc, eid)
    lvl = pl.get("level_id")
    if lvl is None:
        raise LookupError(f"element {eid} has no scheduling level")
    target_z = _level_elevation(doc, lvl) + float(height_above_level_ft)
    dz = target_z - float(pl["m_or"][2])
    plan = M.move_instance(doc, eid, [0.0, 0.0, dz], None, delta=True)
    plan.notes.append(f"mounting height -> {height_above_level_ft:.3f} ft above level {lvl}")
    return plan


def rehost_device(doc: Document, eid: int, new_plane_id: int, *,
                  uv: Optional[Tuple[float, float]] = None, xyz=None):
    """Move a device to ANOTHER face / plane (an existing SketchPlane): its
    ``m_hostId`` is repointed, its placement frame becomes the new plane's
    frame at the new mounting point, and the old plane id is swapped for
    the new one in the header's dependency lists."""
    from .. import manipulate as M
    old = device_placement(doc, eid)
    old_plane = old.get("m_hostId")
    fr = plane_frame(doc, new_plane_id)
    if uv is not None:
        point = _add(_add(fr["or"], fr["X"], float(uv[0])), fr["Y"], float(uv[1]))
    elif xyz is not None:
        p = (float(xyz[0]), float(xyz[1]), float(xyz[2]) if len(xyz) > 2 else fr["or"][2])
        d = tuple(p[i] - fr["or"][i] for i in range(3))
        point = _add(_add(fr["or"], fr["X"], _dot(d, fr["X"])), fr["Y"], _dot(d, fr["Y"]))
    else:
        raise ValueError("pass uv= or xyz= for the new mounting point")
    move = M.move_instance(doc, eid, list(point), None, delta=False)
    m3 = _rows_from_columns(fr["X"], fr["Y"], fr["Z"])
    edit = M.modify_element(doc, eid, {
        "m_hostId": int(new_plane_id),
        "m_pInstanceInfo.value.m_Trf.m_3x3": m3,
    }, kind="rehost", reason=f"re-host device {eid}: plane {old_plane} -> {new_plane_id}")
    plans = [move, edit]
    if isinstance(old_plane, int) and old_plane > 0:
        sess = M.session(doc)
        hdr = sess.value(eid, 101)
        parents = ((hdr.get("m_parents") or {}).get("value")) or {}
        changed = False
        for key in ("m_deletion", "m_regenOnly", "m_appearanceParents"):
            lst = parents.get(key)
            if isinstance(lst, list) and old_plane in lst:
                parents[key] = sorted({(new_plane_id if x == old_plane else x) for x in lst})
                changed = True
        if changed:
            from ..manipulate import ModifyPlan, FieldChange
            hp = ModifyPlan(kind="rehost-header", elem_id=eid, class_name=doc.class_of(eid))
            hp.changes.append(FieldChange(101, "m_parents (host plane swap)",
                                          old_plane, new_plane_id))
            hp.record_edits.append(sess.replacement(eid, 101, "rehost: header parents"))
            sess.plans.append(hp)
            plans.append(hp)
    return plans


def retype_device(doc: Document, eid: int, new_symbol_id: int, *,
                  allow_family_change: bool = False):
    """Swap a device to another loaded type (e.g. Standard -> GFCI)."""
    from .. import manipulate as M
    return M.retype_instance(doc, eid, new_symbol_id,
                             allow_family_change=allow_family_change)


def delete_device(doc: Document, eid: int, *, cascade: bool = True):
    """Delete a device, DETACHING it cleanly: its records leave, its host
    plane stays (shared planes are peers, not dependents), and every element
    that referenced it — its circuit's member connector, the wires drawn to
    it, the panel bookkeeping, its space/room — is neutralised so no
    dangling reference survives.  ``cascade=True`` (default) also removes
    the device's own annotation dependents (its tag); a circuit is a PEER
    and is never deleted with the device (it just loses one member)."""
    from .. import manipulate as M
    plan = M.delete_element(doc, eid, cascade=cascade)
    circuits = [r for r in (plan.referrer_edits or [])
                if r.get("class") == "RbsElectricalSystem"]
    if circuits:
        plan.notes.append(
            f"device was on {len(circuits)} circuit(s) "
            f"{[c['id'] for c in circuits]}: their member connector(s) now "
            f"reference nothing (Revit re-tallies the circuit load on open; an "
            f"emptied circuit may be removed or re-circuited by the user)")
    return plan


# ===========================================================================
# demo / CLI
# ===========================================================================
def _demo(path: str) -> dict:
    doc = Document.from_file(path)
    out = {"file": path, "levels": doc.levels(),
           "device_symbols": device_symbols(doc)[:40],
           "hosting_census": device_census(doc)}
    return out


def main(argv=None) -> int:
    import json
    import os
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))), "samples", "rmebasicsampleproject.rvt")
    print(json.dumps(_demo(path), indent=1, default=str))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

"""rvt.frontdoor.ifc_out -- the VERSION-AGNOSTIC IFC ADDITION.

Why this module exists (target-2025 stream, 2026-08-04): the certified
genesis base is Revit 2026 and Revit CANNOT open newer files, so until the
2025 genesis campaign certifies (docs/writer/genesis-2025-plan.md) a
``--target-version 2025`` request is answered by the 2026 build PLUS one
clear line PLUS **an IFC the user's own Revit CAN consume today** (any
modern Revit links/imports IFC; the IFC spec is release-agnostic).  This
module writes that IFC -- deterministically, from the SAME resolved intent
model every route lands in, with the SAME tagging contract the ``--ifc``
route reads back.

The emitted file is the shape our own resolver (:mod:`rvt.ifc.intent`) is
proven on -- the worked ``inputs/ifc/electrical-room-2500a.ifc`` dialect:

* IFC4, SI metres, project -> site -> building -> one storey PER INTENT LEVEL
  (placed at the level's elevation; every product contained under ITS
  level's storey with level-relative z, so the chain composes to world);
* ONE room-shell ``IfcBuildingElementProxy`` carrying a ``RoomInformation``
  pset and per-wall box solids named ``wall_<i>`` (world-baked
  ``IfcTriangulatedFaceSet``; the resolver re-derives centerlines);
* one product per equipment item (``IfcElectricDistributionBoard`` /
  ``IfcTransformer`` / ...) with a body box named ``<tag>_body`` (floor
  gear) or ``<tag>_enclosure`` (wall gear) plus a thin ``<tag>_nameplate``
  front-feature plate so the resolver recovers the front normal, and the
  tagging-contract pset (PanelSchedule / SwitchboardSchedule /
  TransformerSchedule) as the join key;
* deterministic GlobalIds (md5 of a stable seed) and a pinned header
  timestamp, so the same intent always yields byte-identical IFC.

ROUND TRIP IS THE ACCEPTANCE: ``intent_from_ifc(write_intent_ifc(model))``
must yield the same tags / kinds / wall count (tests/test_target2025.py).

No third-party dependency to WRITE (plain STEP text); reading it back uses
ifcopenshell like every other IFC.  Territory: ``src/rvt/frontdoor/``
(target-2025 stream).
"""
from __future__ import annotations

import hashlib
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["write_intent_ifc"]

#: IFC GlobalId base-64 alphabet (IFC 2.x/4 "compressed GUID")
_G64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

#: pinned header stamp -- the emitter is deterministic by construction
_STAMP = "2026-08-04T00:00:00"

_PSET_BY_KIND = {
    "switchboard": "SwitchboardSchedule",
    "transformer": "TransformerSchedule",
}
_DEFAULT_PSET = "PanelSchedule"

#: enum PredefinedType per kind (IFC4); anything else -> $
_PDT_BY_KIND = {
    "switchboard": "SWITCHBOARD",
    "distribution_panelboard": "DISTRIBUTIONBOARD",
    "lighting_panelboard": "DISTRIBUTIONBOARD",
    "receptacle_panelboard": "DISTRIBUTIONBOARD",
    "panelboard": "DISTRIBUTIONBOARD",
}


def _guid(seed: str) -> str:
    """Deterministic 22-char IFC GlobalId from a stable seed string."""
    n = int.from_bytes(hashlib.md5(seed.encode("utf-8")).digest(), "big")
    # 128 bits = 2 + 21*6: first char in [0,3], then 21 six-bit chars
    out = [_G64[(n >> 126) & 0x3]]
    for i in range(21):
        out.append(_G64[(n >> (120 - 6 * i)) & 0x3F])
    return "".join(out)


def _f(v: float) -> str:
    """STEP REAL: always carries a decimal point, no exponent surprises."""
    s = f"{float(v):.6f}".rstrip("0")
    if s.endswith("."):
        return s
    if "." not in s:
        s += "."
    return s


def _s(v: Any) -> str:
    """STEP string literal (quotes doubled, latin-safe fallback)."""
    t = str(v).replace("'", "''")
    return "'" + t.encode("ascii", "replace").decode("ascii") + "'"


class _W:
    """A tiny STEP writer: add(entity-text) -> '#n' reference."""

    def __init__(self) -> None:
        self.rows: List[str] = []

    def add(self, text: str) -> str:
        self.rows.append(text)
        return f"#{len(self.rows)}"

    def body(self) -> str:
        return "".join(f"#{i + 1}={t};\n" for i, t in enumerate(self.rows))


# ---------------------------------------------------------------------------
# geometry: world-baked boxes (8 corners, 12 triangles)
# ---------------------------------------------------------------------------

_TRIS = "((1,3,2),(1,4,3),(5,6,7),(5,7,8),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,4,8),(3,8,7),(4,1,5),(4,5,8))"


def _box_pts(cx: float, cy: float, ax: float, ay: float,
             half_len: float, half_thick: float, zlo: float, zhi: float
             ) -> List[Tuple[float, float, float]]:
    """8 corners of a plan-rotated box: centre (cx,cy), long axis (ax,ay)
    (unit), half extents along/across, z from ``zlo`` to ``zhi``."""
    tx, ty = -ay, ax                                   # across axis
    corners2 = [(-half_len, -half_thick), (half_len, -half_thick),
                (half_len, half_thick), (-half_len, half_thick)]
    out: List[Tuple[float, float, float]] = []
    for z in (zlo, zhi):
        for u, v in corners2:
            out.append((cx + u * ax + v * tx, cy + u * ay + v * ty, z))
    return out


def _faceset(w: _W, pts: Sequence[Tuple[float, float, float]], style: str,
             name: str) -> str:
    plist = w.add("IFCCARTESIANPOINTLIST3D(("
                  + ",".join(f"({_f(x)},{_f(y)},{_f(z)})" for x, y, z in pts) + "))")
    fs = w.add(f"IFCTRIANGULATEDFACESET({plist},$,$,{_TRIS},$)")
    w.add(f"IFCSTYLEDITEM({fs},({style}),{_s(name)})")
    return fs


# ---------------------------------------------------------------------------
# psets
# ---------------------------------------------------------------------------

def _pval(w: _W, key: str, val: Any) -> Optional[str]:
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCBOOLEAN({'.T.' if val else '.F.'}),$)")
    if isinstance(val, int):
        return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCINTEGER({val}),$)")
    if isinstance(val, float):
        return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCREAL({_f(val)}),$)")
    return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCLABEL({_s(val)}),$)")


def _pset(w: _W, oh: str, owner: str, name: str, props: Dict[str, Any]) -> None:
    refs = [r for r in (_pval(w, k, v) for k, v in props.items()) if r]
    if not refs:
        return
    ps = w.add(f"IFCPROPERTYSET({_s(_guid('pset:' + name + ':' + owner))},{oh},"
               f"{_s(name)},$,({','.join(refs)}))")
    w.add(f"IFCRELDEFINESBYPROPERTIES({_s(_guid('rel:' + name + ':' + owner))},{oh},"
          f"$,$,({owner}),{ps})")


# ---------------------------------------------------------------------------
# THE EMITTER
# ---------------------------------------------------------------------------

def write_intent_ifc(model: Any, path: str, *, note: str = "") -> str:
    """Write ``model`` (the resolved :class:`rvt.ifc.intent.IntentModel`) as
    a deterministic IFC4 file at ``path``; returns ``path``.

    The IFC carries every wall run and every equipment item with its
    tagging-contract pset -- the version-agnostic form of the SAME intent
    the ``.rvt`` build used, re-consumable by ``frontdoor author --ifc``.
    """
    w = _W()
    person = w.add("IFCPERSON($,$,'',$,$,$,$,$)")
    org = w.add("IFCORGANIZATION($,'tekton',$,$,$)")
    po = w.add(f"IFCPERSONANDORGANIZATION({person},{org},$)")
    app = w.add(f"IFCAPPLICATION({org},'1.0','tekton frontdoor IFC addition','tekton_frontdoor')")
    oh = w.add(f"IFCOWNERHISTORY({po},{app},$,.NOCHANGE.,$,$,$,0)")
    dirx = w.add("IFCDIRECTION((1.,0.,0.))")
    dirz = w.add("IFCDIRECTION((0.,0.,1.))")
    origin = w.add("IFCCARTESIANPOINT((0.,0.,0.))")
    a2p = w.add(f"IFCAXIS2PLACEMENT3D({origin},{dirz},{dirx})")
    ctx = w.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{a2p},$)")
    sub = w.add(f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,{ctx},$,.MODEL_VIEW.,$)")
    units = [w.add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)"),
             w.add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)"),
             w.add("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)"),
             w.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)"),
             w.add("IFCSIUNIT(*,.ELECTRICVOLTAGEUNIT.,$,.VOLT.)"),
             w.add("IFCSIUNIT(*,.ELECTRICCURRENTUNIT.,$,.AMPERE.)"),
             w.add("IFCSIUNIT(*,.POWERUNIT.,$,.WATT.)")]
    ua = w.add(f"IFCUNITASSIGNMENT(({','.join(units)}))")
    pname = getattr(model, "project_name", None) or "tekton authored project"
    proj = w.add(f"IFCPROJECT({_s(_guid('project:' + pname))},{oh},{_s(pname)},"
                 f"{_s(note) if note else '$'},$,$,$,({ctx}),{ua})")
    plc_site = w.add(f"IFCLOCALPLACEMENT($,{a2p})")
    site = w.add(f"IFCSITE({_s(_guid('site'))},{oh},'Site',$,$,{plc_site},$,$,.ELEMENT.,$,$,$,$,$)")
    plc_bld = w.add(f"IFCLOCALPLACEMENT({plc_site},{a2p})")
    bld = w.add(f"IFCBUILDING({_s(_guid('building'))},{oh},'Building',$,$,{plc_bld},$,$,.ELEMENT.,$,$,$)")
    # one IfcBuildingStorey per intent level, its placement AT the level's
    # elevation: a product sits under ITS level's storey with level-relative
    # z (Equipment.level / RoomShell.level set), so the storey chain composes
    # back to world z and `frontdoor author --ifc` re-reads the same levels.
    # Only BUILDING STORIES become storeys (a read-back model also lists the
    # source's reference datums, ``is_building_story: False``); a level-blind
    # caller (no object carries a level: world z throughout) gets ONE storey.
    room = getattr(model, "room", None)
    all_levels = list(getattr(model, "levels", None) or [])
    levels = [lv for lv in all_levels if lv.get("is_building_story") is not False] or all_levels
    if not any(getattr(o, "level", None) for o in list(getattr(model, "equipment", None) or []) + [room]):
        levels = levels[:1]
    levels = levels or [{"id": "L1", "name": "Level 1", "elevation": 0.0}]
    storeys: Dict[str, Tuple[str, str, float]] = {}     # level id -> (storey, placement, elev)
    for i, lv in enumerate(levels):
        lid = str(lv.get("id") or f"L{i + 1}")
        lname = str(lv.get("name") or f"Level {i + 1}")
        lelev = float(lv.get("elevation") or 0.0)
        if abs(lelev) > 1e-9:
            lorg = w.add(f"IFCCARTESIANPOINT((0.,0.,{_f(lelev)}))")
            lax = w.add(f"IFCAXIS2PLACEMENT3D({lorg},{dirz},{dirx})")
        else:
            lax = a2p
        plc_sto = w.add(f"IFCLOCALPLACEMENT({plc_bld},{lax})")
        sto = w.add(f"IFCBUILDINGSTOREY({_s(_guid('storey:' + lid + ':' + lname))},{oh},"
                    f"{_s(lname)},$,$,{plc_sto},$,$,.ELEMENT.,{_f(lelev)})")
        storeys[lid] = (sto, plc_sto, lelev)
    #: level-less objects carry WORLD z: they go under the storey nearest 0,
    #: rebased on it (z - its elevation)
    ground_id = min(storeys, key=lambda k: (abs(storeys[k][2]), storeys[k][2]))

    def storey_for(level: Optional[str]) -> Tuple[str, str, float]:
        """(storey, its placement, z to subtract) for an object's level."""
        if level in storeys:
            sto_, plc_, _elev = storeys[str(level)]
            return sto_, plc_, 0.0
        sto_, plc_, elev_ = storeys[ground_id]
        return sto_, plc_, elev_

    w.add(f"IFCRELAGGREGATES({_s(_guid('agg:project'))},{oh},$,$,{proj},({site}))")
    w.add(f"IFCRELAGGREGATES({_s(_guid('agg:site'))},{oh},$,$,{site},({bld}))")
    w.add(f"IFCRELAGGREGATES({_s(_guid('agg:building'))},{oh},$,$,{bld},"
          f"({','.join(s for s, _p, _e in storeys.values())}))")

    # one shared surface style
    rgb = w.add("IFCCOLOURRGB($,0.611765,0.635294,0.639216)")
    rend = w.add(f"IFCSURFACESTYLERENDERING({rgb},0.,$,$,$,$,$,$,.NOTDEFINED.)")
    sstyle = w.add(f"IFCSURFACESTYLE('tekton_gray',.BOTH.,({rend}))")
    style = w.add(f"IFCPRESENTATIONSTYLEASSIGNMENT(({sstyle}))")

    products: Dict[str, List[str]] = {}                 # storey -> contained products

    # ---- the room shell proxy (wall_<i> box solids) ------------------------
    if room is not None and getattr(room, "walls", None):
        sto, plc_sto, zoff = storey_for(getattr(room, "level", None))
        items: List[str] = []
        for i, wr in enumerate(room.walls, start=1):
            p0 = list(map(float, wr.p0_m))[:2]
            p1 = list(map(float, wr.p1_m))[:2]
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            ln = math.hypot(dx, dy) or 1.0
            ax, ay = dx / ln, dy / ln
            base = float(getattr(wr, "base_m", 0.0) or 0.0) - zoff
            th = float(wr.thickness_m)
            items.append(_faceset(
                w, _box_pts((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0, ax, ay,
                            ln / 2.0 + th / 2.0, th / 2.0,
                            base, base + float(wr.height_m)),
                style, f"wall_{i}"))
        shape = w.add(f"IFCSHAPEREPRESENTATION({sub},'Body','Tessellation',({','.join(items)}))")
        rep = w.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({shape}))")
        plc = w.add(f"IFCLOCALPLACEMENT({plc_sto},{a2p})")
        rname = f"{getattr(room, 'name', None) or 'Electrical Room'} room shell"
        proxy = w.add(f"IFCBUILDINGELEMENTPROXY({_s(_guid('shell:' + rname))},{oh},"
                      f"{_s(rname)},$,$,{plc},{rep},$,$)")
        products.setdefault(sto, []).append(proxy)
        info = dict(getattr(room, "info", None) or {})
        if not info:
            clear = dict(getattr(room, "clear", None) or {})
            info = {"RoomName": getattr(room, "name", None),
                    "ClearWidth": clear.get("clearWidth_m"),
                    "ClearDepth": clear.get("clearDepth_m"),
                    "ClearHeight": clear.get("clearHeight_m")}
        _pset(w, oh, proxy, "RoomInformation", info)

    # ---- equipment ---------------------------------------------------------
    for eq in getattr(model, "equipment", None) or []:
        kind = str(getattr(eq, "kind", "") or "")
        tag = str(getattr(eq, "tag", "") or "EQ")
        dims = dict(getattr(eq, "dims_m", None) or {})
        wd = float(dims.get("w", 0.6))
        dd = float(dims.get("d", 0.3))
        hh = float(dims.get("h", 1.2))
        sto, plc_sto, zoff = storey_for(getattr(eq, "level", None))
        ins = list(map(float, getattr(eq, "insertion_m", [0.0, 0.0, 0.0])))
        ins[2] -= zoff                                   # z relative to ITS storey
        fr = list(map(float, (getattr(eq, "front_normal", None) or [0.0, -1.0, 0.0])))[:2]
        fl = math.hypot(*fr) or 1.0
        fx, fy = fr[0] / fl, fr[1] / fl                 # front normal (out of the face)
        wx, wy = -fy, fx                                # width axis
        upright = str(getattr(eq, "frame_kind", "yaw")) == "upright"
        if upright:
            # insertion = centre of the enclosure BACK face; z = centre height
            cx, cy = ins[0] + fx * dd / 2.0, ins[1] + fy * dd / 2.0
            zlo, zhi = ins[2] - hh / 2.0, ins[2] + hh / 2.0
            body_name = f"{tag}_enclosure"
        else:
            # insertion = footprint centre at the body base
            cx, cy = ins[0], ins[1]
            zlo, zhi = ins[2], ins[2] + hh
            body_name = f"{tag}_body"
        items = [_faceset(w, _box_pts(cx, cy, wx, wy, wd / 2.0, dd / 2.0, zlo, zhi),
                          style, body_name)]
        # thin nameplate proud of the front face at 2/3 height: the resolver's
        # front-normal vote
        pcx = cx + fx * (dd / 2.0 + 0.003)
        pcy = cy + fy * (dd / 2.0 + 0.003)
        pz = zlo + (zhi - zlo) * 2.0 / 3.0
        items.append(_faceset(w, _box_pts(pcx, pcy, wx, wy, 0.12, 0.003,
                                          pz - 0.022, pz + 0.022),
                              style, f"{tag}_nameplate"))
        shape = w.add(f"IFCSHAPEREPRESENTATION({sub},'Body','Tessellation',({','.join(items)}))")
        rep = w.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({shape}))")
        plc = w.add(f"IFCLOCALPLACEMENT({plc_sto},{a2p})")
        cls = str(getattr(eq, "ifc_class", "") or "IfcElectricDistributionBoard")
        if cls.lower() not in ("ifcelectricdistributionboard", "ifctransformer",
                               "ifcswitchingdevice", "ifcbuildingelementproxy"):
            cls = "IfcElectricDistributionBoard"
        pdt = _PDT_BY_KIND.get(kind) if cls.lower() == "ifcelectricdistributionboard" else None
        name = str(getattr(eq, "name", None) or tag)
        prod = w.add(f"{cls.upper()}({_s(_guid('eq:' + tag))},{oh},{_s(name)},$,$,"
                     f"{plc},{rep},{_s(tag)},{('.' + pdt + '.') if pdt else '$'})")
        products.setdefault(sto, []).append(prod)
        contract = {k: v for k, v in (getattr(eq, "contract", None) or {}).items()
                    if not str(k).startswith("_") and v not in (None, "")}
        # the feeder tree rides as FedFrom (the reader rebuilds edges from it)
        fed = contract.get("FedFrom") or getattr(eq, "fed_from", None)
        if not fed:
            for ed in getattr(model, "feeders", None) or []:
                if str(getattr(ed, "target", "")) == tag and getattr(ed, "source", None):
                    fed = str(ed.source)
                    break
        if fed and str(fed).upper() != "SERVICE":
            contract["FedFrom"] = str(fed)
        man = {k: contract.pop(k) for k in ("Manufacturer", "ModelLabel")
               if k in contract}
        _pset(w, oh, prod, _PSET_BY_KIND.get(kind, _DEFAULT_PSET), contract)
        if man:
            _pset(w, oh, prod, "Pset_ManufacturerTypeInformation", man)

    for lid, (sto, _plc, _elev) in storeys.items():
        if products.get(sto):
            w.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE({_s(_guid('contains:storey:' + lid))},{oh},"
                  f"$,$,({','.join(products[sto])}),{sto})")

    fname = os.path.basename(path)
    text = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n"
        f"FILE_NAME({_s(fname)},'{_STAMP}',(''),(''),"
        "'tekton frontdoor IFC addition','tekton frontdoor','');\n"
        "FILE_SCHEMA(('IFC4'));\n"
        "ENDSEC;\n"
        "DATA;\n"
        + w.body() +
        "ENDSEC;\n"
        "END-ISO-10303-21;\n")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="ascii") as fh:
        fh.write(text)
    return path

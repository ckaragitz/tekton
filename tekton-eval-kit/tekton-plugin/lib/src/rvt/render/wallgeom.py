"""rvt.render.wallgeom -- BAKED wall geometry, native-exact (genesis-11 RENDER track).

LOAD is not RENDER.  Every viewer certification through ORCHESTRATOR VERDICTS
#22 is a TRANSLATION pass: the model tree of our joined-walls file holds only
the level node ('L1 - Ground Floor [311]', ours) and the walls emit NO viewable
geometry -- the walls+panel file translates to "Design is empty".  Desktop
Revit REGENERATES an element's solid from its definition on open; Autodesk's
cloud translator's ``RevitExtractor`` does NOT -- it draws only the BAKED
B-rep a Revit save caches for every model element as its seq-103 record.
Our created walls carry a ``SerializedDummy`` there (``rvt.mutate.add_wall``
sets ``rep=None``: acceptance bet T1 "Revit regenerates", which the desktop
does and the viewer does not).  This module CONSTRUCTS the baked rep native
walls carry, in the native grammar, from the wall's own definition -- and
provides the two write paths (create-time and existing-file in place).

THE NATIVE WALL REP GRAMMAR (mined this session over rst / rme walls; the full
evidence, offsets and the leaf-for-leaf reproduction of a native unjoined
wall live in ``docs/inbox/render-emit.md``).  A straight, unjoined,
single-run wall's seq-103 record is a ``GElement`` (0x89e)::

    GElement { m_GInfo{ cat = the Walls-category PROJECTION GStyleElem id
                        (30 in the rst lineage), tag = element id, ctl 0,
                        flags 557060 },
      m_subNodes = [
        # 4 x GGroup = the WallRefPlanesGStep reference planes (category =
        #   the -2000896 GStyle, EXCLUDED from 3D views -> graphics-hidden);
        #   node order by history KEY (39, 30, 29, 40); each ->
        #   Geometry -> 1 open planar quad Face (rs = the Default material)
        #   + 4 single-face Edges + 1 EdgeLoop + Plane,
        # 1 x Geometry (cat -1) = the SOLID = the BaseWallGStep box:
        #   6 planar Faces + 12 Edges + 6 EdgeLoops + 6 Planes + 6 GFillings.
        #   The box is the ELEVATION rectangle (length x height) extruded
        #   through the THICKNESS: caps = the two long faces (history keys
        #   [2] = the key-29 compound-structure side plane, [1] = the key-30
        #   side), sides = start/finish/bottom/top (keys [3,0..3]); rails
        #   [1,curve,cap], laterals [2,curve,next-curve] -- the SAME box
        #   topology rvt.famgen.geometry authors for family extrusions.
      ],
      m_bBox = m_tightbBox = the solid's world AABB (ft),
      m_elementId = element id, m_gElemType 3, m_flags 0 }

Every leaf below the shape (frames, uv envelopes, edge uv end points,
per-face GFilling placer, flags per key, materials) is DERIVED from the wall's
location line + base elevation + height + the type's layer offsets/material
-- and READ from the wall's own seq-102 object wherever the object already
states it (the location GLine, ``m_pRefFaces``, the ``BaseWallGStep`` /
``WallRefPlanesGStep`` tag tables), so the rep is CONSISTENT WITH THE
OBJECT'S OWN GEOMETRY HISTORY BY CONSTRUCTION.  Archive pids are assigned by
``rvt.famgen.geometry.assign_pids`` and reproduce Revit's numbering exactly
(root subnodes 3.., group geometries next, solid faces, solid edges, group
faces/edges, then loops/fillings/planes -- verified against the natives).

REPRODUCTION PROOF: ``reproduce_native_wall`` rebuilds a native wall's rep
from that wall's own object + type and diffs it leaf-by-leaf against the
wall's real seq-103 record; ``python -m rvt.render.wallgeom reproduce`` runs
it on the rme unjoined specimen (the diff is EMPTY modulo the garbage field
``Geometry.m_GInfo.m_controlCommand``, see ``GARBAGE_CONTROL_COMMAND``).

Public API::

    spec = wall_render_spec(doc, wall_id)           # facts from the object + doc
    rep  = build_wall_gelement(spec)                 # the seq-103 GElement dict
    audit_wall_rep(rep)                              # topology / weakref / uv audit -> []
    normalize_geometry_history(obj, spec)            # canonical UNJOINED seq-102 bookkeeping
    bake_planned_wall(doc, new_element)              # create-time: NewElement.rep = rep
    bake_wall_geometry(src_rvt, out_rvt, wall_ids)   # existing file: in-place substitution

CLI (``python -m rvt.render.wallgeom``): ``reproduce`` (the native proof),
``bake IN OUT [ids...]`` (existing file), ``room`` / ``min`` / ``all``
(the ifc-room render probes on the certified genesis base), ``audit FILE``.

Territory: this module + tests/test_render_wallgeom.py +
experiments/ifc_room/render/* + docs/inbox/render-emit.md.  Every
dependency (rvt.famgen.geometry / genesis.types / mutate / regadd / commit /
encode / objects / render.inspect) is IMPORTED, never edited.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..genesis.types import blank_object, INVALID
from ..famgen.geometry import (
    assign_pids, ginfo, plane, _ptr, _weak, _sym, _number_graph,
    _v, _sub, _add, _mul, _dot, _cross, _norm, _unit, _neg, _cv, _uv, _clean,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
Vec = Sequence[float]

# ===========================================================================
# 1. class ids / built-in ids
# ===========================================================================

CLASS_GELEMENT = 0x089E          #: seq-103 rep class we author
CLASS_SERIALIZED_DUMMY = 0x0F2C  #: the empty rep our created walls carried
CLASS_SWALL = 0x0F02             #: seq-102 SWall

OST_WALLS = -2000011             #: built-in Walls category
OST_WALL_REFPLANES = -2000896    #: the reference-plane geometry category
                                 #: (GStyle 24925 in the rst lineage;
                                 #: EXCLUDED from 3D views by the standard
                                 #: draw filters -> the ref planes never draw)
OST_GFILLING = -2000540          #: GFilling.m_GInfo category (GStyle 32/33)

BIP_WALL_HEIGHT = -1001101       #: SWall computed height (ft)  [V]
BIP_WALL_USER_HEIGHT = -1001105  #: SWall unconnected height (ft) [V]

# ===========================================================================
# 2. grammar constants (verified on rst 493879 / rst 1115258 / rme 573386)
# ===========================================================================

#: GElement root m_GInfo.m_flags [V, 3/3 walls]
GELEM_ROOT_FLAGS = 557060
#: Geometry m_GInfo.m_flags (solid AND ref-plane geometries) [V]
GEOMETRY_GINFO_FLAGS = 573444
#: Geometry.m_flags [V]
GEOMETRY_MFLAGS = 7
#: Geometry.m_tessEpsCntrl.m_TessEpsCntrlVersion (2026 files) [V]
TESS_VERSION = 1
#: solid CAP faces (the two long faces, keys [1]/[2]) m_GInfo.m_flags [V]
CAP_FACE_GIFLAGS = 557572
#: solid THIN side faces (keys [3,0..3]) m_GInfo.m_flags [V]
SIDE_FACE_GIFLAGS = 558596
#: solid Edge m_GInfo.m_flags [V] (== famgen EDGE_INFO_FLAGS)
EDGE_GIFLAGS = 557572
#: EdgeLoop / GFilling m_GInfo.m_flags [V] (== famgen LOOP_INFO_FLAGS)
LOOP_GIFLAGS = 524292
GFILLING_GIFLAGS = 524292
#: Face.m_faceFlags_v9: solid faces / ref-plane faces [V]
FACE_FLAGS_V9_SOLID = 4
FACE_FLAGS_V9_REFPLANE = 36
#: Edge.m_flags: 6 = stored direction is FORWARD in m_pFace[0]'s loop,
#: 7 = REVERSED there (famgen EDGE_FLAGS_FORWARD/REVERSED_IN_A) [V]
EDGE_FLAGS_FORWARD = 6
EDGE_FLAGS_REVERSED = 7
#: GFilling.m_flags / m_fillColor when the material has NO surface pattern
#: (every rme wall face, and the thin faces of the patterned rst walls) [V]
GFILLING_FLAGS_NOPATTERN = 18
GFILLING_COLOR_NONE = 16777216            # 0x1000000
#: GFilling.m_flags when a surface pattern IS drawn (rst concrete caps) [V]
GFILLING_FLAGS_PATTERN = 8

#: GElement.m_gElemType of a model element rep [V]
GELEM_TYPE_ELEMENT = 3

#: Geometry.m_GInfo.m_controlCommand is a per-element GARBAGE bit field in
#: the natives (differs between two walls of the SAME file: rst 493879 =
#: 84115474, rst 1115258 = 67272737; FamilySymbol geometries mostly 0) --
#: NOT a checksum / semantic value.  We write 0 (a value native geometry
#: nodes also carry).  [V corpus census, ctlcmd.py]
GARBAGE_CONTROL_COMMAND = 0

# --- the WallRefPlanesGStep planes -----------------------------------------
#: The four reference planes a straight wall's ``WallRefPlanesGStep``
#: names by history KEY.  29 / 30 = the two compound-structure SIDE planes
#: (``CompoundStructure.m_segRefFaceKeys`` maps them to the grid's two
#: vertical segments); 39 / 40 = the two CENTRE planes (core centre /
#: location line).  The rep's GGroup NODE ORDER is by key: 39, 30, 29, 40
#: (native node tags run 4,3,2,1) [V, 3/3 walls].
REFPLANE_NODE_KEYS = (39, 30, 29, 40)
#: GGroup.m_GInfo.m_flags per plane key [V, 3/3 walls]
REFPLANE_GGROUP_FLAGS = {39: 168329380, 30: 34111648, 29: 34111648, 40: 168329892}
#: the ref-plane Face's m_GInfo.m_flags per key [V]
REFPLANE_FACE_GIFLAGS = {39: 67665924, 30: 67665920, 29: 67665920, 40: 67666436}
#: the ref-plane Edges' m_GInfo.m_flags per key [V]
REFPLANE_EDGE_GIFLAGS = {39: 557060, 30: 557056, 29: 557056, 40: 557572}

# --- the BaseWallGStep box --------------------------------------------------
#: face history keys (m_faceHist.m_keys[:2]) -> role.  CAP2 = the key-29
#: compound side plane (the box's first cap: origin frame at the location
#: line, xVec = +wall direction); CAP1 = the key-30 side (xVec = -direction).
FACEKEY_CAP2 = (2, -1)
FACEKEY_CAP1 = (1, -1)
FACEKEY_START = (3, 0)       #: end face at the location line's START point
FACEKEY_FINISH = (3, 1)      #: end face at the FINISH point
FACEKEY_BOTTOM = (3, 2)      #: bottom face (z = base)
FACEKEY_TOP = (3, 3)         #: top face (z = base + height)
#: profile-curve numbering of the four thin faces (the [3,k] index k)
CURVE_START, CURVE_FINISH, CURVE_BOTTOM, CURVE_TOP = 0, 1, 2, 3
#: CYCLE order of the profile curves = the CCW boundary of the elevation
#: rectangle in CAP2's frame (u along the wall, v up): bottom -> finish ->
#: top -> start.  The lateral [2,i,j] joins CONSECUTIVE cycle curves. [V]
CYCLE = (CURVE_BOTTOM, CURVE_FINISH, CURVE_TOP, CURVE_START)
#: relative tag layout of the box (offset from the box base tag B), by
#: history key -- identical in rst (B=8), rst 1115258 (B=5), rme (B=5) and
#: the famgen family box (B=0 with caps swapped) [V]:
BOX_FACE_TAG_OFFSET = {FACEKEY_CAP2: 0, FACEKEY_CAP1: 1, FACEKEY_BOTTOM: 2,
                       FACEKEY_FINISH: 5, FACEKEY_TOP: 9, FACEKEY_START: 13}
#: edge keys: rails (1, curve, cap-side) with side 0 = CAP2, 1 = CAP1;
#: laterals (2, curve_i, curve_j) with (i, j) consecutive in CYCLE.
BOX_EDGE_TAG_OFFSET = {
    (1, CURVE_BOTTOM, 0): 3, (1, CURVE_BOTTOM, 1): 4,
    (1, CURVE_FINISH, 0): 6, (1, CURVE_FINISH, 1): 7,
    (2, CURVE_BOTTOM, CURVE_FINISH): 8,
    (1, CURVE_TOP, 0): 10, (1, CURVE_TOP, 1): 11,
    (2, CURVE_FINISH, CURVE_TOP): 12,
    (1, CURVE_START, 0): 14, (1, CURVE_START, 1): 15,
    (2, CURVE_TOP, CURVE_START): 16,
    (2, CURVE_START, CURVE_BOTTOM): 17,
}
#: the twelve edge keys in SERIALIZATION order (= ascending tag) [V]
BOX_EDGE_KEY_ORDER = [k for k, _ in sorted(BOX_EDGE_TAG_OFFSET.items(), key=lambda kv: kv[1])]
#: the six face keys in SERIALIZATION order (= ascending tag) [V]
BOX_FACE_KEY_ORDER = [k for k, _ in sorted(BOX_FACE_TAG_OFFSET.items(), key=lambda kv: kv[1])]

Z_UP = [0.0, 0.0, 1.0]


# ===========================================================================
# 3. the render spec (every fact the constructor needs)
# ===========================================================================

@dataclass
class RefPlane:
    """One WallRefPlanesGStep reference plane, as the wall object states it."""
    key: int                    # 29 / 30 / 39 / 40
    tag: int                    # history tag (m_pRefFaces face tag)
    origin: List[float]         # plane origin (ft, world)
    xvec: List[float]           # = wall direction
    yvec: List[float]           # = +Z
    envelope: List[List[float]] # [[0,0],[length, height]]

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class WallRenderSpec:
    """The complete, self-contained recipe of one straight wall's rep.

    All geometry in FEET / world coordinates.  ``origin``/``direction``/
    ``t0``/``t1`` describe the location GLine (points = origin +
    t*direction, t in [t0, t1]); ``left`` = the horizontal left normal
    ``(-dir.y, dir.x, 0)``; the two compound side planes (history keys 29
    and 30) sit at signed offsets along ``left``.  The box's CAP2 face
    (history key [2]) is ALWAYS the plane at the MINIMUM offset (the -left
    side) and CAP1 (key [1]) the one at the MAXIMUM offset -- regardless
    of which compound key (29 or 30) sits there [V: rme 573386 key29 =
    min side; rme 573735 / 575873 key29 = MAX side; CAP2 = min in all].
    """
    elem_id: int
    origin: List[float]
    direction: List[float]
    t0: float
    t1: float
    base_z: float
    height: float
    off_min: float                      # CAP2 (key [2]) side offset along left
    off_max: float                      # CAP1 (key [1]) side offset along left
    off_key29: Optional[float] = None   # provenance: the compound key-29 plane offset
    off_key30: Optional[float] = None   # provenance: the compound key-30 plane offset
    ref_planes: List[RefPlane] = dc_field(default_factory=list)
    face_tags: Dict[Tuple[int, int], int] = dc_field(default_factory=dict)
    edge_tags: Dict[Tuple[int, int, int], int] = dc_field(default_factory=dict)
    tag_source: str = "history"         # 'history' | 'canonical'
    base_tag: int = 5                   # B (informational)
    material_id: int = INVALID          # the four thin faces' m_renderStyleId
                                        # (= layers[0]'s material; single-layer: THE material)
    material_cap2: Optional[int] = None # CAP2 (min side) material; None -> material_id
    material_cap1: Optional[int] = None # CAP1 (max side) material; None -> material_id
    root_category_id: int = INVALID     # root GInfo category (Walls GStyle id)
    refplane_category_id: int = INVALID # GGroup category (-2000896 GStyle id)
    refplane_material_id: int = INVALID # ref-plane faces' m_renderStyleId
    fill_category_id: int = INVALID     # GFilling GInfo category (-2000540 GStyle)
    pattern_id: int = INVALID           # material surface pattern (else -1)
    pattern_color: int = 0
    with_ref_planes: bool = True
    with_fillings: bool = True
    control_command: int = GARBAGE_CONTROL_COMMAND
    tess_version: int = TESS_VERSION
    notes: List[str] = dc_field(default_factory=list)
    warnings: List[str] = dc_field(default_factory=list)

    # -- derived --------------------------------------------------------
    @property
    def length(self) -> float:
        return float(self.t1 - self.t0)

    @property
    def thickness(self) -> float:
        return abs(float(self.off_max) - float(self.off_min))

    @property
    def left(self) -> List[float]:
        d = self.direction
        return [-d[1], d[0], 0.0]

    @property
    def top_z(self) -> float:
        return self.base_z + self.height

    def point(self, t: float, offset: float, z: float) -> List[float]:
        """World point at line parameter ``t``, side ``offset``, elevation ``z``."""
        o, d, L = self.origin, self.direction, self.left
        return [_clean(o[0] + d[0] * t + L[0] * offset),
                _clean(o[1] + d[1] * t + L[1] * offset),
                _clean(z)]

    def anchor(self) -> List[float]:
        """The GFilling placer anchor: the location line START point at the
        base elevation (verified: every native placer origin = this point
        projected onto the face's uv)."""
        return self.point(self.t0, 0.0, self.base_z)

    def corners(self) -> Dict[Tuple[str, str, str], List[float]]:
        """The 8 box corners keyed (end, side, level): end in ('s','e'),
        side in ('n' = the CAP2/min side, 'x' = the CAP1/max side), level in
        ('b','t')."""
        out = {}
        for end, t in (("s", self.t0), ("e", self.t1)):
            for side, off in (("n", self.off_min), ("x", self.off_max)):
                for lvl, z in (("b", self.base_z), ("t", self.top_z)):
                    out[(end, side, lvl)] = self.point(t, off, z)
        return out

    def bbox_exact(self) -> List[List[float]]:
        """The solid's exact world AABB (native m_bBox == m_tightbBox for an
        unjoined wall)."""
        pts = list(self.corners().values())
        return [[min(p[k] for p in pts) for k in range(3)],
                [max(p[k] for p in pts) for k in range(3)]]

    def bbox(self) -> List[List[float]]:
        return self.bbox_exact()

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["face_tags"] = {str(k): v for k, v in self.face_tags.items()}
        d["edge_tags"] = {str(k): v for k, v in self.edge_tags.items()}
        d["length"] = self.length
        d["thickness"] = self.thickness
        return d


class WallRenderError(Exception):
    """The wall object does not carry what a straight box rep needs."""


# ===========================================================================
# 4. reading the facts off the wall object / document
# ===========================================================================

def _val(x):
    """Unwrap a decoded pointer holder to its value dict (or {})."""
    if isinstance(x, dict) and "ptr_class" in x:
        v = x.get("value")
        return v if isinstance(v, dict) else {}
    return x if isinstance(x, dict) else {}


def _param_double(obj: dict, param_id: int) -> Optional[float]:
    pset = _val(obj.get("m_pParamValueSetDouble")).get("m_paramSet") or []
    for p in pset:
        if isinstance(p, dict) and p.get("m_paramId") == param_id:
            v = p.get("m_value")
            if isinstance(v, (int, float)):
                return float(v)
    return None


def location_line(obj: dict) -> Tuple[List[float], List[float], float, float]:
    """(origin, unit direction, t0, t1) of the wall's location GLine (ft).

    Raises :class:`WallRenderError` for non-line drivers (arc walls are a
    different B-rep: cylindrical faces -- not authored here)."""
    drv = _val(obj.get("m_pCurveDriver"))
    crv_holder = drv.get("m_pCrv")
    ccls = crv_holder.get("ptr_class") if isinstance(crv_holder, dict) else None
    if ccls not in (None, "GLine"):
        raise WallRenderError(f"wall driver curve is {ccls}: only straight (GLine) "
                              "walls are supported by the box rep")
    crv = _val(crv_holder)
    org = crv.get("m_origin")
    dvec = crv.get("m_dirVec")
    ep = crv.get("m_endParams")
    if not (org and dvec and ep and len(ep) >= 2):
        raise WallRenderError("wall object carries no location GLine "
                              "(m_pCurveDriver.m_pCrv origin/dirVec/endParams)")
    n = math.hypot(float(dvec[0]), float(dvec[1]))
    if n <= 1e-12:
        raise WallRenderError("degenerate location line direction")
    d = [float(dvec[0]) / n, float(dvec[1]) / n, 0.0]
    t0, t1 = float(ep[0]), float(ep[1])
    if not t1 - t0 > 1e-9:
        raise WallRenderError(f"non-positive wall length: endParams {ep}")
    return [float(org[0]), float(org[1]), float(org[2])], d, t0, t1


def wall_height(obj: dict, header: Optional[dict] = None) -> float:
    """The wall's height (ft): BIP -1001101 (computed height), else
    -1001105 (unconnected height), else the header bounding box extent."""
    for bip in (BIP_WALL_HEIGHT, BIP_WALL_USER_HEIGHT):
        h = _param_double(obj, bip)
        if h is not None and h > 1e-6:
            return h
    if header:
        bb = _val(header.get("m_pBBox")).get("m_minmax")
        if bb and len(bb) == 2:
            dz = float(bb[1][2]) - float(bb[0][2])
            if dz > 1e-6:
                return dz
    raise WallRenderError("wall height not determinable (no height params, no header bbox)")


def _refplanes_step(obj: dict) -> dict:
    gsl = _val(obj.get("m_geomSteps"))
    for s in gsl.get("m_nonBRepGList") or []:
        if isinstance(s, dict) and s.get("ptr_class") == "WallRefPlanesGStep":
            return _val(s)
    return {}


def _basewall_step(obj: dict) -> dict:
    gsl = _val(obj.get("m_geomSteps"))
    for s in gsl.get("m_bRepFormGList") or []:
        if isinstance(s, dict) and s.get("ptr_class") == "BaseWallGStep":
            return _val(s)
    return {}


def refplane_key_by_tag(obj: dict) -> Dict[int, int]:
    """{ref-face tag: history key} from the wall's WallRefPlanesGStep."""
    out = {}
    for e in _refplanes_step(obj).get("m_faceHistTable") or []:
        keys = (e.get("m_faceHist") or {}).get("m_keys") or []
        if keys:
            out[int(e.get("m_id"))] = int(keys[0])
    return out


def box_tags_from_history(obj: dict) -> Tuple[Dict[Tuple[int, int], int],
                                            Dict[Tuple[int, int, int], int], bool]:
    """(face_tags, edge_tags, complete) as the wall's BaseWallGStep declares.

    Face keys are the first two m_keys of each face-history entry (cap keys
    [1,-1] / [2,-1], side keys [3,k]); edge keys the first three (rails
    [1,curve,cap], laterals [2,curve_i,curve_j]).  ``complete`` = all six
    faces + twelve edges of the box are named."""
    bws = _basewall_step(obj)
    faces: Dict[Tuple[int, int], int] = {}
    for e in bws.get("m_faceHistTable") or []:
        keys = (e.get("m_faceHist") or {}).get("m_keys") or []
        if len(keys) >= 2:
            faces[(int(keys[0]), int(keys[1]))] = int(e.get("m_id"))
    edges: Dict[Tuple[int, int, int], int] = {}
    for e in bws.get("m_edgeHistTable") or []:
        keys = (e.get("m_edgeHist") or {}).get("m_keys") or []
        if len(keys) >= 3:
            edges[(int(keys[0]), int(keys[1]), int(keys[2]))] = int(e.get("m_id"))
    complete = (all(k in faces for k in BOX_FACE_TAG_OFFSET)
                and all(k in edges for k in BOX_EDGE_TAG_OFFSET))
    return faces, edges, complete


def canonical_box_tags(base_tag: int) -> Tuple[Dict[Tuple[int, int], int],
                                              Dict[Tuple[int, int, int], int]]:
    """The box's face/edge tags for base tag ``B`` (the corpus layout:
    B = number of tags the WallRefPlanesGStep consumed, tags 0..B-1)."""
    faces = {k: int(base_tag) + off for k, off in BOX_FACE_TAG_OFFSET.items()}
    edges = {k: int(base_tag) + off for k, off in BOX_EDGE_TAG_OFFSET.items()}
    return faces, edges


def ref_planes_from_object(obj: dict) -> List[RefPlane]:
    """The wall's driven reference planes (``m_pRefFaces``), each labelled
    with its history KEY via the WallRefPlanesGStep tag table."""
    key_by_tag = refplane_key_by_tag(obj)
    out: List[RefPlane] = []
    for f in obj.get("m_pRefFaces") or []:
        fv = _val(f)
        tag = (fv.get("m_GInfo") or {}).get("m_tag")
        surf = _val(fv.get("m_pSurf"))
        o, x, y = surf.get("m_origin"), surf.get("m_xVec"), surf.get("m_yVec")
        env = (surf.get("m_Envelope") or {}).get("m_corners")
        if tag is None or not (o and x and y and env):
            continue
        key = key_by_tag.get(int(tag))
        if key is None:
            continue
        out.append(RefPlane(key=int(key), tag=int(tag), origin=_cv(o), xvec=_cv(x),
                            yvec=_cv(y),
                            envelope=[[float(env[0][0]), float(env[0][1])],
                                      [float(env[1][0]), float(env[1][1])]]))
    return out


# --- document lookups ------------------------------------------------------

def gstyle_for_category(doc, builtin_category: int, *, projection_only: bool = True) -> int:
    """The host document's GStyleElem for a built-in category (the
    PROJECTION style, m_gstyleType 1, preferred; lowest id).  -1 if absent."""
    best = None
    for eid in doc.ids_of_class("GStyleElem"):
        v = doc.value(eid) or {}
        if v.get("m_categoryId") != builtin_category:
            continue
        gt = v.get("m_gstyleType")
        if projection_only and gt is not None and gt != 1:
            continue
        if best is None or eid < best:
            best = eid
    return int(best) if best is not None else INVALID


def layer_material(doc, wall_type_id: int) -> int:
    """The wall type's structural (else first) layer material, if that
    MaterialElem exists in the document; else -1."""
    tv = doc.value(wall_type_id) or {}
    cs = _val(tv.get("m_pCompoundStructure"))
    layers = cs.get("m_layers") or []
    idx = cs.get("m_structuralMaterialLayerIndex")
    order = []
    if isinstance(idx, int) and 0 <= idx < len(layers):
        order.append(layers[idx])
    order.extend(layers)
    for L in order:
        mid = (L or {}).get("m_materialId")
        if isinstance(mid, int) and mid > 0 and doc.exists(mid):
            return int(mid)
    return INVALID


def type_thickness(doc, wall_type_id: int) -> Optional[float]:
    """Sum of the wall type's compound layer widths (ft), or None."""
    tv = doc.value(wall_type_id) or {}
    cs = _val(tv.get("m_pCompoundStructure"))
    layers = cs.get("m_layers") or []
    total = 0.0
    for L in layers:
        w = (L or {}).get("m_layerWidth")
        if isinstance(w, (int, float)):
            total += float(w)
    return total if total > 1e-9 else None


def exterior_side_offsets(doc, wall_type_id: int, w29: float, w30: float
                          ) -> Optional[Tuple[float, float, dict]]:
    """The world offsets (along the left normal) of the wall SOLID's two
    exterior side faces, derived from the type's compound-structure grid.

    The reference planes 29/30 are the grid segments named by
    ``CompoundStructure.m_segRefFaceKeys`` -- for a SINGLE-layer type they
    ARE the exterior faces; for a multi-layer type they are the STRUCTURAL
    layer's boundaries (interior planes) [V: rme type 563418 'STB 25.0 WD
    12.0': keys 29/30 at grid coords 0.1312/0.9514, exterior at
    -0.2625/0.9514, solid 1.2139 ft thick].  The grid-coordinate -> world
    map is affine; two known points (keys 29 and 30 in both frames) fix its
    sign (the m_isFlipped effect) and origin, then the exterior faces are
    the grid's min/max vertical segments.  Returns (off_min, off_max, info)
    or None when underivable (caller falls back to the key planes)."""
    tv = doc.value(wall_type_id) or {}
    cs = _val(tv.get("m_pCompoundStructure"))
    if not cs:
        return None
    vr = _val(cs.get("m_oVertRegStructure"))
    segs = (vr.get("m_grid") or {}).get("m_segments") or []
    vert = {}                                  # segment id -> cs coordinate
    for s in segs:
        if s.get("m_orientation") == 0 and isinstance(s.get("m_id"), int):
            vert[int(s["m_id"])] = float(s.get("m_coordinate") or 0.0)
    if len(vert) < 2:
        return None
    keymap = {}                                # key -> cs coordinate
    for e in cs.get("m_segRefFaceKeys") or []:
        sid, key = e.get("m_id"), e.get("m_key0")
        if isinstance(sid, int) and isinstance(key, int) and int(sid) in vert:
            keymap[int(key)] = vert[int(sid)]
    if 29 not in keymap or 30 not in keymap:
        return None
    cs29, cs30 = keymap[29], keymap[30]
    cs_min, cs_max = min(vert.values()), max(vert.values())
    if abs(cs29 - cs30) < 1e-9:
        return None
    s = (float(w29) - float(w30)) / (cs29 - cs30)         # ~ +1 or -1 (flip)
    if abs(abs(s) - 1.0) > 1e-3:
        return None                                       # not a rigid map: distrust
    c0 = cs29 - float(w29) / s                             # cs coord of the location line
    wa, wb = s * (cs_min - c0), s * (cs_max - c0)         # world offsets of cs_min / cs_max
    # per-side layer materials [V rme 575873; the layer list runs from the
    # cs_min side (layers[0]) to the cs_max side (layers[-1])]
    layers = cs.get("m_layers") or []
    mat_first = (layers[0] or {}).get("m_materialId") if layers else INVALID
    mat_last = (layers[-1] or {}).get("m_materialId") if layers else INVALID
    mat_at_min = mat_first if wa <= wb else mat_last       # material at the world-min side
    mat_at_max = mat_last if wa <= wb else mat_first
    info = {"grid_vertical_segments": vert, "key_coords": keymap, "sign": s,
            "line_coord": c0, "exterior_offsets": [min(wa, wb), max(wa, wb)],
            "keys_are_exterior": (abs(min(cs29, cs30) - cs_min) < 1e-6
                                  and abs(max(cs29, cs30) - cs_max) < 1e-6),
            "material_min_side": mat_at_min, "material_max_side": mat_at_max,
            "material_first_layer": mat_first, "layers": len(layers)}
    return min(wa, wb), max(wa, wb), info


def material_surface_pattern(doc, material_id: int) -> Tuple[int, int]:
    """(surface pattern id, surface pattern colour) of a MaterialElem;
    (-1, 0) when the material or the pattern element is absent."""
    if not (isinstance(material_id, int) and material_id > 0):
        return INVALID, 0
    mv = doc.value(material_id) or {}
    mat = _val(mv.get("m_pMaterial"))
    pid = mat.get("m_surfacePatternId")
    color = mat.get("m_surfacePatternColor") or 0
    if isinstance(pid, int) and pid > 0 and doc.exists(pid):
        return int(pid), int(color)
    return INVALID, 0


def default_material(doc) -> int:
    """The document's 'Default' material (native ref-plane faces reference
    it: id 24 in the samples), by name; -1 if none."""
    if doc.exists(24) and (doc.class_of(24) or "") == "MaterialElem":
        return 24
    for eid in doc.ids_of_class("MaterialElem"):
        v = doc.value(eid) or {}
        name = (_val(v.get("m_pMaterial")).get("m_name") or "")
        if name.strip().lower() in ("default", "default wall", "<default>"):
            return int(eid)
    return INVALID


def geometry_control_command(doc, exclude_id: Optional[int] = None) -> int:
    """The Geometry-node m_controlCommand to write.  Kept as a hook: the
    field is per-element garbage in the natives (see
    :data:`GARBAGE_CONTROL_COMMAND`), so we return 0."""
    return GARBAGE_CONTROL_COMMAND


# ===========================================================================
# 5. wall_render_spec  --  assemble the recipe
# ===========================================================================

def wall_render_spec(doc, wall, *, header: Optional[dict] = None,
                     elem_id: Optional[int] = None,
                     root_category_id: Optional[int] = None,
                     refplane_material_id: Optional[int] = None,
                     material_id: Optional[int] = None,
                     with_ref_planes: bool = True,
                     with_fillings: bool = True) -> WallRenderSpec:
    """Build the :class:`WallRenderSpec` of a wall.

    ``doc`` -- a :class:`rvt.mutate.Document` (for the type / material /
    category-style lookups; may be ``None`` if every id is passed).
    ``wall`` -- an element id (of ``doc``), a decoded seq-102 SWall object
    dict, or a :class:`rvt.mutate.NewElement`` (``.obj`` / ``.header`` /
    ``.elem_id``).  The optional keyword ids override the document lookups
    (``root_category_id`` = the Walls-category GStyle to name; ``material_id``
    = the solid faces' material).
    """
    obj, hdr, wid = _resolve_wall(doc, wall, header, elem_id)
    org, d, t0, t1 = location_line(obj)
    base_z = float(org[2])
    height = wall_height(obj, hdr)
    left = [-d[1], d[0], 0.0]

    # --- reference planes + side offsets (from the object's own planes) ----
    planes = ref_planes_from_object(obj)
    off_by_key: Dict[int, float] = {}
    for rp in planes:
        off_by_key[rp.key] = _dot(_sub(_v(rp.origin), _v(org)), left)
    notes: List[str] = []
    warnings: List[str] = []
    off29 = off_by_key.get(29)
    off30 = off_by_key.get(30)
    if off29 is None or off30 is None:
        # no side planes: centre the type thickness on the location line
        wt_id = obj.get("m_WallAttributesId")
        thick = type_thickness(doc, wt_id) if doc is not None and wt_id else None
        if thick is None:
            raise WallRenderError("no key-29/30 ref planes and no wall type thickness: "
                                  "cannot place the box side faces")
        off29, off30 = -thick / 2.0, thick / 2.0
        warnings.append(f"side planes missing (keys present {sorted(off_by_key)}): "
                        f"centred the type thickness {thick:.4f} ft on the location line")
    if abs(float(off30) - float(off29)) < 1e-9:
        raise WallRenderError("degenerate wall thickness (key-29 and key-30 planes coincide)")
    off_min, off_max = min(float(off29), float(off30)), max(float(off29), float(off30))
    # multi-layer types: keys 29/30 may be INTERIOR layer boundaries -- the
    # solid's exterior faces come from the compound grid's outer segments
    wt_id = obj.get("m_WallAttributesId")
    ext = (exterior_side_offsets(doc, wt_id, float(off29), float(off30))
           if (doc is not None and wt_id) else None)
    mat_cap2 = mat_cap1 = mat_thin = None
    if ext is not None:
        e_min, e_max, e_info = ext
        if not e_info.get("keys_are_exterior"):
            notes.append(f"compound keys 29/30 are interior layer boundaries "
                         f"(grid {e_info.get('key_coords')}); solid exterior faces "
                         f"taken from the grid's outer segments -> offsets "
                         f"[{e_min:.4f}, {e_max:.4f}] ft")
        off_min, off_max = float(e_min), float(e_max)
        if int(e_info.get("layers") or 0) > 1:
            # multi-layer: caps carry their exterior layer's material, the
            # four thin faces the FIRST layer's [V rme 575873, 1 specimen]
            m_min = e_info.get("material_min_side")
            m_max = e_info.get("material_max_side")
            m_first = e_info.get("material_first_layer")
            if all(isinstance(m, int) and m > 0 and doc.exists(m)
                   for m in (m_min, m_max, m_first)):
                mat_cap2, mat_cap1, mat_thin = int(m_min), int(m_max), int(m_first)
                notes.append(f"multi-layer materials: cap2(min side) {mat_cap2}, "
                             f"cap1(max side) {mat_cap1}, thin faces {mat_thin} "
                             f"[hypothesis: thin faces = first layer, 1 specimen]")

    # --- history tags -----------------------------------------------------
    face_tags, edge_tags, complete = box_tags_from_history(obj)
    tag_source = "history"
    ref_tags = [rp.tag for rp in planes]
    base_tag = min(face_tags[FACEKEY_CAP2], face_tags[FACEKEY_CAP1]) if complete else None
    if not complete:
        # a wall without a box-shaped history: allocate the canonical layout
        # right after the ref-plane tags (the caller must then emit a
        # matching BaseWallGStep -- see normalize_geometry_history)
        base = 1 + max(ref_tags) if ref_tags else 1
        face_tags, edge_tags = canonical_box_tags(base)
        base_tag = base
        tag_source = "canonical"
        notes.append(f"BaseWallGStep tag tables incomplete -> canonical box tags "
                     f"allocated from base tag {base}")

    # --- material / category / pattern lookups -----------------------------
    wt_id = obj.get("m_WallAttributesId")
    if material_id is not None:
        mat = int(material_id)
        mat_cap2 = mat_cap1 = None
    elif mat_thin is not None:
        mat = int(mat_thin)
    else:
        mat = layer_material(doc, wt_id) if (doc is not None and wt_id) else INVALID
    if mat == INVALID:
        warnings.append("solid material unresolved (type layer material absent) -> "
                        "m_renderStyleId -1 (category default appearance)")
    pattern_id, pattern_color = (material_surface_pattern(doc, mat) if doc is not None
                                 else (INVALID, 0))
    if pattern_id != INVALID:
        warnings.append(f"material {mat} has surface pattern {pattern_id}: emitted "
                        f"patternId + colour with m_data null [hypothesis: the "
                        f"extractor tessellates faces regardless of pattern data]")
    root_cat = root_category_id
    if root_cat is None:
        root_cat = gstyle_for_category(doc, OST_WALLS) if doc is not None else INVALID
        if root_cat == INVALID:
            root_cat = 30 if (doc is not None and doc.exists(30)
                              and (doc.class_of(30) or "") == "GStyleElem") else INVALID
        if root_cat == INVALID:
            warnings.append("no Walls-category projection GStyleElem in this document: "
                            "root GInfo category = -1 (the rst lineage's row 30 is one "
                            "of the GC'd catalog rows -- see the ADD-cat rung)")
    refcat = gstyle_for_category(doc, OST_WALL_REFPLANES) if doc is not None else INVALID
    fillcat = gstyle_for_category(doc, OST_GFILLING) if doc is not None else INVALID
    refmat = refplane_material_id if refplane_material_id is not None else (
        default_material(doc) if doc is not None else INVALID)

    spec = WallRenderSpec(
        elem_id=int(wid), origin=_cv(org), direction=_cv(d), t0=t0, t1=t1,
        base_z=base_z, height=float(height), off_min=off_min, off_max=off_max,
        off_key29=(float(off_by_key[29]) if 29 in off_by_key else None),
        off_key30=(float(off_by_key[30]) if 30 in off_by_key else None),
        ref_planes=planes, face_tags=face_tags,
        edge_tags=edge_tags, tag_source=tag_source,
        base_tag=int(base_tag) if base_tag is not None else 5,
        material_id=int(mat), material_cap2=mat_cap2, material_cap1=mat_cap1,
        root_category_id=int(root_cat),
        refplane_category_id=int(refcat), refplane_material_id=int(refmat),
        fill_category_id=int(fillcat), pattern_id=int(pattern_id),
        pattern_color=int(pattern_color), with_ref_planes=bool(with_ref_planes),
        with_fillings=bool(with_fillings), notes=notes, warnings=warnings)
    return spec


def _resolve_wall(doc, wall, header, elem_id):
    """Normalise the ``wall`` argument to (object dict, header dict|None, id)."""
    if isinstance(wall, int):
        if doc is None:
            raise ValueError("wall id given but doc is None")
        obj = doc.value(wall)
        if not isinstance(obj, dict):
            raise WallRenderError(f"element {wall} not decodable in the document")
        h = None
        try:
            hd = doc.decode(wall, 101)
            h = hd.value if hd is not None else None
        except Exception:
            h = None
        return obj, (header or h), int(elem_id if elem_id is not None else wall)
    if hasattr(wall, "obj") and hasattr(wall, "elem_id"):        # NewElement
        return wall.obj, (header or getattr(wall, "header", None)), int(
            elem_id if elem_id is not None else wall.elem_id)
    if isinstance(wall, dict):
        wid = elem_id if elem_id is not None else wall.get("m_id")
        if wid is None:
            raise ValueError("elem_id required with a bare object dict")
        return wall, header, int(wid)
    raise TypeError(f"unsupported wall argument {type(wall)!r}")


# ===========================================================================
# 6. the constructor
# ===========================================================================

def _plane_frame(origin: Vec, xvec: Vec, yvec: Vec):
    """(origin, xvec, yvec, project) with project(p) -> uv in this frame."""
    o, x, y = _v(origin), _v(xvec), _v(yvec)

    def project(p: Vec) -> List[float]:
        dp = _sub(_v(p), o)
        return _uv([_dot(dp, x), _dot(dp, y)])
    return o, x, y, project


def _face_frames(spec: WallRenderSpec) -> Dict[Tuple[int, int], dict]:
    """The six solid faces' plane frames (origin / xVec / yVec / uv envelope
    / outward normal), keyed by face key.  The exact frame conventions of a
    native wall solid [V, 3/3 rme walls, docs/inbox/render-emit.md sec. G3]
    (min = the CAP2 side offset ``off_min``, max = ``off_max``)::

        CAP2  : origin = O + off_min*L (at the LINE origin O, base z),
                xVec = D, yVec = Z, env u in [t0, t1], v in [0, H]
        CAP1  : origin = O + off_max*L, xVec = -D, yVec = Z,
                env u in [-t1, -t0], v in [0, H]
        BOTTOM: origin = P(start, min, base), xVec = L, yVec = D,  env [0,T]x[0,len]
        FINISH: origin = P(end,   min, base), xVec = L, yVec = Z,  env [0,T]x[0,H]
        TOP   : origin = P(end,   min, top),  xVec = L, yVec = -D, env [0,T]x[0,len]
        START : origin = P(start, min, top),  xVec = L, yVec = -Z, env [0,T]x[0,H]
    """
    D = spec.direction
    L = spec.left
    O = spec.origin
    z0, z1 = spec.base_z, spec.top_z
    H, T, length = spec.height, spec.thickness, spec.length
    t0, t1 = spec.t0, spec.t1
    lo, hi = spec.off_min, spec.off_max
    negD = _neg(D)
    negZ = [0.0, 0.0, -1.0]
    frames = {}
    frames[FACEKEY_CAP2] = dict(
        origin=[O[0] + L[0] * lo, O[1] + L[1] * lo, z0],
        xvec=list(D), yvec=list(Z_UP), env=[[t0, 0.0], [t1, H]],
        normal=_neg(L))                       # outward = away from the max side
    frames[FACEKEY_CAP1] = dict(
        origin=[O[0] + L[0] * hi, O[1] + L[1] * hi, z0],
        xvec=negD, yvec=list(Z_UP), env=[[-t1, 0.0], [-t0, H]],
        normal=list(L))
    frames[FACEKEY_BOTTOM] = dict(
        origin=spec.point(t0, lo, z0), xvec=list(L), yvec=list(D),
        env=[[0.0, 0.0], [T, length]], normal=list(negZ))
    frames[FACEKEY_FINISH] = dict(
        origin=spec.point(t1, lo, z0), xvec=list(L), yvec=list(Z_UP),
        env=[[0.0, 0.0], [T, H]], normal=list(D))
    frames[FACEKEY_TOP] = dict(
        origin=spec.point(t1, lo, z1), xvec=list(L), yvec=negD,
        env=[[0.0, 0.0], [T, length]], normal=list(Z_UP))
    frames[FACEKEY_START] = dict(
        origin=spec.point(t0, lo, z1), xvec=list(L), yvec=list(negZ),
        env=[[0.0, 0.0], [T, H]], normal=list(negD))
    for f in frames.values():
        f["origin"] = _cv(f["origin"])
        f["xvec"] = _cv(f["xvec"])
        f["yvec"] = _cv(f["yvec"])
        _, _, _, proj = _plane_frame(f["origin"], f["xvec"], f["yvec"])
        f["project"] = proj
    return frames


def _sign(x: float) -> float:
    return 1.0 if x >= 0 else -1.0


def _edge_definitions(spec: WallRenderSpec) -> Dict[Tuple[int, int, int], dict]:
    """The 12 box edges: (faces[A,B], p_first, p_last, m_flags) per edge
    key.  Directions are the natives' stored directions [V]: each RAIL is
    stored FORWARD in its cap's loop (CAP2's loop runs the elevation
    rectangle CCW: bottom +D, finish +Z, top -D, start -Z; CAP1's loop is
    the reverse cycle); the closing lateral (V0 = start^bottom) runs
    min->max side (flags 6), the other three laterals run max->min (7)."""
    c = spec.corners()          # (end, side, level) -> point; side 'n'=min, 'x'=max
    S, E, B, T = "s", "e", "b", "t"
    N, X = "n", "x"
    ED = {}
    # rails on CAP2 (side 0, the min side) -- forward in CAP2's CCW loop
    ED[(1, CURVE_BOTTOM, 0)] = dict(faces=[FACEKEY_CAP2, FACEKEY_BOTTOM],
                                    p0=c[(S, N, B)], p1=c[(E, N, B)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_FINISH, 0)] = dict(faces=[FACEKEY_CAP2, FACEKEY_FINISH],
                                    p0=c[(E, N, B)], p1=c[(E, N, T)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_TOP, 0)] = dict(faces=[FACEKEY_CAP2, FACEKEY_TOP],
                                 p0=c[(E, N, T)], p1=c[(S, N, T)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_START, 0)] = dict(faces=[FACEKEY_CAP2, FACEKEY_START],
                                   p0=c[(S, N, T)], p1=c[(S, N, B)], flags=EDGE_FLAGS_FORWARD)
    # rails on CAP1 (side 1, the max side) -- forward in CAP1's (reverse-cycle) loop
    ED[(1, CURVE_START, 1)] = dict(faces=[FACEKEY_CAP1, FACEKEY_START],
                                   p0=c[(S, X, B)], p1=c[(S, X, T)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_TOP, 1)] = dict(faces=[FACEKEY_CAP1, FACEKEY_TOP],
                                 p0=c[(S, X, T)], p1=c[(E, X, T)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_FINISH, 1)] = dict(faces=[FACEKEY_CAP1, FACEKEY_FINISH],
                                    p0=c[(E, X, T)], p1=c[(E, X, B)], flags=EDGE_FLAGS_FORWARD)
    ED[(1, CURVE_BOTTOM, 1)] = dict(faces=[FACEKEY_CAP1, FACEKEY_BOTTOM],
                                    p0=c[(E, X, B)], p1=c[(S, X, B)], flags=EDGE_FLAGS_FORWARD)
    # laterals [2, curve_i, curve_j] at the CYCLE vertices; pFace = [face(j), face(i)]
    #   V0 = start ^ bottom : (2, START, BOTTOM), min -> max, flags 6 (closing)
    #   V1 = bottom ^ finish: (2, BOTTOM, FINISH), max -> min, flags 7
    #   V2 = finish ^ top   : (2, FINISH, TOP),    max -> min, flags 7
    #   V3 = top ^ start    : (2, TOP, START),     max -> min, flags 7
    ED[(2, CURVE_START, CURVE_BOTTOM)] = dict(faces=[FACEKEY_BOTTOM, FACEKEY_START],
                                              p0=c[(S, N, B)], p1=c[(S, X, B)],
                                              flags=EDGE_FLAGS_FORWARD)
    ED[(2, CURVE_BOTTOM, CURVE_FINISH)] = dict(faces=[FACEKEY_FINISH, FACEKEY_BOTTOM],
                                                p0=c[(E, X, B)], p1=c[(E, N, B)],
                                                flags=EDGE_FLAGS_REVERSED)
    ED[(2, CURVE_FINISH, CURVE_TOP)] = dict(faces=[FACEKEY_TOP, FACEKEY_FINISH],
                                             p0=c[(E, X, T)], p1=c[(E, N, T)],
                                             flags=EDGE_FLAGS_REVERSED)
    ED[(2, CURVE_TOP, CURVE_START)] = dict(faces=[FACEKEY_START, FACEKEY_TOP],
                                            p0=c[(S, X, T)], p1=c[(S, N, T)],
                                            flags=EDGE_FLAGS_REVERSED)
    return ED


#: FACEKEY of the thin face swept by profile curve k
_CURVE_FACE = {CURVE_START: FACEKEY_START, CURVE_FINISH: FACEKEY_FINISH,
               CURVE_BOTTOM: FACEKEY_BOTTOM, CURVE_TOP: FACEKEY_TOP}


def _loop_orders() -> Dict[Tuple[int, int], List[Tuple[int, int, int]]]:
    """Per solid face, its EdgeLoop's edge keys in loop order [V]:

    * CAP2: the CYCLE rails on side 0 -- (bottom, finish, top, start)
    * CAP1: the reversed cycle on side 1 -- (start, top, finish, bottom)
    * side face of curve k (cycle position i): [rail(k,0), lateral at the
      cycle vertex where k STARTS, rail(k,1), lateral at the vertex where
      k ENDS] -- famgen's [rail_start, lat(vertex i), rail_end, lat(vertex i+1)].
    """
    loops = {
        FACEKEY_CAP2: [(1, k, 0) for k in CYCLE],
        FACEKEY_CAP1: [(1, k, 1) for k in reversed(CYCLE)],
    }
    n = len(CYCLE)
    for i, k in enumerate(CYCLE):
        prev_k = CYCLE[(i - 1) % n]       # curve ending at k's start vertex
        next_k = CYCLE[(i + 1) % n]       # curve starting at k's end vertex
        lat_start = (2, prev_k, k)         # lateral at the vertex where k starts
        lat_end = (2, k, next_k)           # lateral at the vertex where k ends
        loops[_CURVE_FACE[k]] = [(1, k, 0), lat_start, (1, k, 1), lat_end]
    return loops


def _fill_dir_world(spec: WallRenderSpec, normal: Vec) -> List[float]:
    """The GFilling placer direction in WORLD terms [V, 6/6 faces of the
    native rme wall + the caps of the rst walls]: vertical faces = the
    horizontal in-plane direction ``Z x n_out``; horizontal faces (whose
    ``Z x n_out`` vanishes) = the wall direction."""
    zc = _cross(Z_UP, _v(normal))
    if _norm(zc) < 1e-9:
        return list(spec.direction)
    return _unit(zc)


def _gfilling(spec: WallRenderSpec, face_sym: str, frame: dict) -> dict:
    """One solid face's GFilling (the material surface-pattern placement)."""
    proj = frame["project"]
    anchor = spec.anchor()
    dw = _fill_dir_world(spec, frame["normal"])
    o, x, y = _v(frame["origin"]), _v(frame["xvec"]), _v(frame["yvec"])
    dir_uv = _uv([_dot(dw, x), _dot(dw, y)])
    g = blank_object("GFilling")
    g["m_GInfo"] = ginfo(category=spec.fill_category_id, tag=-1,
                          control_command=0, flags=GFILLING_GIFLAGS)
    g["m_pGFace"] = _sym(face_sym)
    g["m_placer"] = {"m_scale": 1.0, "m_origin": proj(anchor), "m_dir": dir_uv,
                     "m_uvScale": [1.0, 1.0], "m_isMirrored": False,
                     "m_placedDraft": False}
    g["m_data"] = None
    if spec.pattern_id != INVALID:
        g["m_patternId"] = int(spec.pattern_id)
        g["m_fillColor"] = int(spec.pattern_color)
        g["m_flags"] = GFILLING_FLAGS_PATTERN
    else:
        g["m_patternId"] = INVALID
        g["m_fillColor"] = GFILLING_COLOR_NONE
        g["m_flags"] = GFILLING_FLAGS_NOPATTERN
    return _ptr("GFilling", g)


def _edge_loop(face_sym: str, first_edge_sym: str, last_edge_sym: str,
               env: List[List[float]]) -> dict:
    lp = blank_object("EdgeLoop")
    lp["m_GInfo"] = ginfo(flags=LOOP_GIFLAGS)
    lp["m_nextLoop"] = None
    lp["m_pFace"] = _sym(face_sym)
    lp["m_next"] = _sym(first_edge_sym)
    lp["m_prev"] = _sym(last_edge_sym)
    lp["m_Envelope"] = {"m_corners": [_uv(env[0]), _uv(env[1])]}
    lp["m_open"] = False
    return lp


def _solid_geometry(spec: WallRenderSpec, registry: Dict[str, dict]) -> dict:
    """The wall's SOLID Geometry node (6 faces, 12 edges, symbolic links)."""
    frames = _face_frames(spec)
    edefs = _edge_definitions(spec)
    loops = _loop_orders()

    def fsym(fk):
        return f"F{fk[0]}_{fk[1]}"

    def esym(ek):
        return f"E{ek[0]}_{ek[1]}_{ek[2]}"

    def lsym(fk):
        return f"L{fk[0]}_{fk[1]}"

    # --- faces (ascending tag = serialization order) ---------------------
    face_ptrs = []
    for fk in BOX_FACE_KEY_ORDER:
        fr = frames[fk]
        tag = int(spec.face_tags[fk])
        order = loops[fk]
        f = blank_object("Face")
        f["m_GInfo"] = ginfo(tag=tag, control_command=0,
                              flags=(CAP_FACE_GIFLAGS if fk in (FACEKEY_CAP2, FACEKEY_CAP1)
                                     else SIDE_FACE_GIFLAGS))
        loop = _edge_loop(fsym(fk), esym(order[0]), esym(order[-1]), fr["env"])
        f["m_pFirstLoop"] = _ptr("EdgeLoop", loop)
        registry[lsym(fk)] = f["m_pFirstLoop"]
        f["m_faceRegions"] = []
        if spec.with_fillings:
            f["m_pGFilling"] = _gfilling(spec, fsym(fk), fr)
        else:
            f["m_pGFilling"] = None
        f["m_oBackgroundFilling"] = None
        if fk == FACEKEY_CAP2 and spec.material_cap2 is not None:
            f["m_renderStyleId"] = int(spec.material_cap2)
        elif fk == FACEKEY_CAP1 and spec.material_cap1 is not None:
            f["m_renderStyleId"] = int(spec.material_cap1)
        else:
            f["m_renderStyleId"] = int(spec.material_id)
        f["m_cutType"] = 0
        f["m_faceFlags_v9"] = FACE_FLAGS_V9_SOLID
        f["m_pSurf"] = plane(fr["origin"], fr["xvec"], fr["yvec"], fr["env"])
        ptr = _ptr("Face", f)
        registry[fsym(fk)] = ptr
        face_ptrs.append(ptr)

    # --- edges (ascending tag = serialization order) ---------------------
    edge_ptrs = []
    for ek in BOX_EDGE_KEY_ORDER:
        d = edefs[ek]
        fa, fb = d["faces"]
        tag = int(spec.edge_tags[ek])
        # neighbours in each adjacent face's loop
        links = []
        for fk in (fa, fb):
            order = loops[fk]
            i = order.index(ek)
            nxt = esym(order[i + 1]) if i + 1 < len(order) else lsym(fk)
            prv = esym(order[i - 1]) if i > 0 else lsym(fk)
            links.append((nxt, prv))
        e = blank_object("Edge")
        e["m_GInfo"] = ginfo(tag=tag, control_command=0, flags=EDGE_GIFLAGS)
        e["m_pFace"] = [_sym(fsym(fa)), _sym(fsym(fb))]
        e["m_next"] = [_sym(links[0][0]), _sym(links[1][0])]
        e["m_prev"] = [_sym(links[0][1]), _sym(links[1][1])]
        e["m_interiorEdgePnts"] = []
        e["m_firstAndLastEdgePnts"] = [
            {"uv": [frames[fa]["project"](d["p0"]), frames[fb]["project"](d["p0"])]},
            {"uv": [frames[fa]["project"](d["p1"]), frames[fb]["project"](d["p1"])]},
        ]
        e["m_flags"] = int(d["flags"])
        ptr = _ptr("Edge", e)
        registry[esym(ek)] = ptr
        edge_ptrs.append(ptr)

    geom = blank_object("Geometry")
    geom["m_GInfo"] = ginfo(category=INVALID, tag=-1,
                             control_command=spec.control_command,
                             flags=GEOMETRY_GINFO_FLAGS)
    geom["m_pFaces"] = face_ptrs
    geom["m_flags"] = GEOMETRY_MFLAGS
    geom["m_geometryTag"] = INVALID
    geom["m_tessEpsCntrl"] = {"m_type": 0, "m_TessEpsCntrlVersion": int(spec.tess_version)}
    geom["m_pEdges"] = edge_ptrs
    geom["m_sharedSurfInfo"] = []
    return _ptr("Geometry", geom)


def _refplane_node(spec: WallRenderSpec, rp: RefPlane, index: int,
                   registry: Dict[str, dict]) -> dict:
    """One ``GGroup(cat = the ref-plane GStyle) -> Geometry -> 1 open
    planar quad Face + 4 single-face Edges`` node [V grammar]."""
    key = rp.key
    env = rp.envelope
    ulen = float(env[1][0] - env[0][0])
    vlen = float(env[1][1] - env[0][1])
    u0, v0 = float(env[0][0]), float(env[0][1])
    u1, v1 = u0 + ulen, v0 + vlen
    # quad corners in the face's own uv, CCW
    uv = [[u0, v0], [u1, v0], [u1, v1], [u0, v1]]
    fs = f"RF{index}"
    ls = f"RL{index}"
    es = [f"RE{index}_{i}" for i in range(4)]

    face = blank_object("Face")
    face["m_GInfo"] = ginfo(tag=-1, control_command=0,
                             flags=REFPLANE_FACE_GIFLAGS.get(key, 67665920))
    loop = _edge_loop(fs, es[0], es[3], env)
    face["m_pFirstLoop"] = _ptr("EdgeLoop", loop)
    registry[ls] = face["m_pFirstLoop"]
    face["m_faceRegions"] = []
    face["m_pGFilling"] = None
    face["m_oBackgroundFilling"] = None
    face["m_renderStyleId"] = int(spec.refplane_material_id)
    face["m_cutType"] = 0
    face["m_faceFlags_v9"] = FACE_FLAGS_V9_REFPLANE
    face["m_pSurf"] = plane(rp.origin, rp.xvec, rp.yvec, env)
    fptr = _ptr("Face", face)
    registry[fs] = fptr

    edge_ptrs = []
    egif = REFPLANE_EDGE_GIFLAGS.get(key, 557056)
    for i in range(4):
        a = uv[i]
        b = uv[(i + 1) % 4]
        e = blank_object("Edge")
        e["m_GInfo"] = ginfo(tag=-1, control_command=0, flags=egif)
        e["m_pFace"] = [_sym(fs), _weak(0)]
        e["m_next"] = [_sym(es[i + 1]) if i + 1 < 4 else _sym(ls), _weak(0)]
        e["m_prev"] = [_sym(es[i - 1]) if i > 0 else _sym(ls), _weak(0)]
        e["m_interiorEdgePnts"] = []
        e["m_firstAndLastEdgePnts"] = [{"uv": [_uv(a), [0.0, 0.0]]},
                                        {"uv": [_uv(b), [0.0, 0.0]]}]
        e["m_flags"] = EDGE_FLAGS_FORWARD
        ptr = _ptr("Edge", e)
        registry[es[i]] = ptr
        edge_ptrs.append(ptr)

    geom = blank_object("Geometry")
    geom["m_GInfo"] = ginfo(category=INVALID, tag=-1,
                             control_command=spec.control_command,
                             flags=GEOMETRY_GINFO_FLAGS)
    geom["m_pFaces"] = [fptr]
    geom["m_flags"] = GEOMETRY_MFLAGS
    geom["m_geometryTag"] = INVALID
    geom["m_tessEpsCntrl"] = {"m_type": 0, "m_TessEpsCntrlVersion": int(spec.tess_version)}
    geom["m_pEdges"] = edge_ptrs
    geom["m_sharedSurfInfo"] = []

    grp = blank_object("GGroup")
    grp["m_GInfo"] = ginfo(category=int(spec.refplane_category_id), tag=int(rp.tag),
                            control_command=0,
                            flags=REFPLANE_GGROUP_FLAGS.get(key, 34111648))
    grp["m_subNodes"] = [_ptr("Geometry", geom)]
    return _ptr("GGroup", grp)


def build_wall_gelement(spec: WallRenderSpec) -> dict:
    """Construct the seq-103 ``GElement`` (the baked rep) of the wall
    described by ``spec``.  Returns an encoder-ready dict (archive pids
    assigned, all weak references resolved)."""
    registry: Dict[str, dict] = {}
    subnodes: List[dict] = []
    if spec.with_ref_planes and spec.ref_planes:
        by_key = {rp.key: rp for rp in spec.ref_planes}
        i = 0
        for key in REFPLANE_NODE_KEYS:
            rp = by_key.get(key)
            if rp is None:
                continue
            subnodes.append(_refplane_node(spec, rp, i, registry))
            i += 1
    subnodes.append(_solid_geometry(spec, registry))

    bbox = spec.bbox()
    tight = spec.bbox_exact()
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(category=int(spec.root_category_id), tag=int(spec.elem_id),
                             control_command=0, flags=GELEM_ROOT_FLAGS)
    root["m_subNodes"] = subnodes
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(tight[0]), _cv(tight[1])]
    root["m_elementId"] = int(spec.elem_id)
    root["m_gElemType"] = GELEM_TYPE_ELEMENT
    root["m_flags"] = 0
    # number the archive object graph + resolve the symbolic weak references
    _number_graph(root, registry)
    _assert_pid_stable(root)
    return root


def _assert_pid_stable(obj: dict) -> None:
    """Re-run the archive numbering on a copy and assert nothing moves (the
    encoder writes ``dict['pid']`` verbatim -- see rvt.encode)."""
    a = copy.deepcopy(obj)
    assign_pids(a)
    if a != obj:
        raise AssertionError("rvt.render.wallgeom: pid layout unstable under assign_pids")


# ===========================================================================
# 7. the audit  (works on OUR reps and on native reps)
# ===========================================================================

def _walk_registered(v, table: Dict[int, str]) -> None:
    """pid -> class of every registered (indexed) object in a rep tree."""
    if isinstance(v, dict):
        if "ptr_class" in v:
            pid = v.get("pid")
            if isinstance(pid, int) and pid > 0:
                table[pid] = v["ptr_class"]
            _walk_registered(v.get("value"), table)
        else:
            for x in v.values():
                _walk_registered(x, table)
    elif isinstance(v, list):
        for x in v:
            _walk_registered(x, table)


def audit_wall_rep(rep: dict, *, spec: Optional[WallRenderSpec] = None) -> List[str]:
    """Structural / topological / geometric audit of a wall rep.

    Returns a list of problem strings (EMPTY = the rep passes every check):
    root shape, solid face/edge counts, unique tags, weakref targets (edge
    faces are Faces, loop links are Edges / EdgeLoops, loop.m_pFace is its
    Face, GFilling.m_pGFace is its Face), closed 4-edge loops per solid
    face, edge uv end points consistent between the two adjacent face
    frames (the 3D reconstructions agree), envelopes containing the loop
    points, and (with ``spec``) tags == the wall's declared history tags.
    """
    probs: List[str] = []
    if not isinstance(rep, dict):
        return ["rep is not a dict"]
    for k in ("m_GInfo", "m_subNodes", "m_bBox", "m_tightbBox", "m_elementId",
              "m_gElemType", "m_flags"):
        if k not in rep:
            probs.append(f"root missing field {k}")
    if probs:
        return probs
    nodes = rep.get("m_subNodes") or []
    solids = [n for n in nodes if n.get("ptr_class") == "Geometry"]
    groups = [n for n in nodes if n.get("ptr_class") == "GGroup"]
    if len(solids) != 1:
        probs.append(f"expected exactly 1 solid Geometry subnode, found {len(solids)}")
    if rep.get("m_gElemType") != GELEM_TYPE_ELEMENT:
        probs.append(f"m_gElemType {rep.get('m_gElemType')} != {GELEM_TYPE_ELEMENT}")
    pid_class: Dict[int, str] = {}
    _walk_registered(rep, pid_class)

    def wr_ok(x, classes, path, allow_zero=True):
        if not isinstance(x, dict) or "weakref" not in x:
            probs.append(f"{path}: not a weakref")
            return
        t = x["weakref"]
        if t == 0:
            if not allow_zero:
                probs.append(f"{path}: null weakref")
            return
        c = pid_class.get(t)
        if c is None:
            probs.append(f"{path}: weakref {t} -> no registered object")
        elif c not in classes:
            probs.append(f"{path}: weakref {t} -> {c}, expected {classes}")

    # --- the solid ------------------------------------------------------
    for sidx, sptr in enumerate(solids):
        s = sptr.get("value") or {}
        faces = s.get("m_pFaces") or []
        edges = s.get("m_pEdges") or []
        if (len(faces), len(edges)) != (6, 12):
            probs.append(f"solid {sidx}: faces/edges {len(faces)}/{len(edges)} != 6/12")
        ftags = [(f.get("value") or {}).get("m_GInfo", {}).get("m_tag") for f in faces]
        etags = [(e.get("value") or {}).get("m_GInfo", {}).get("m_tag") for e in edges]
        if len(set(ftags)) != len(ftags):
            probs.append(f"solid {sidx}: duplicate face tags {ftags}")
        if len(set(etags)) != len(etags):
            probs.append(f"solid {sidx}: duplicate edge tags {etags}")
        if spec is not None:
            want_f = sorted(spec.face_tags.values())
            want_e = sorted(spec.edge_tags.values())
            if sorted(t for t in ftags if t is not None) != want_f:
                probs.append(f"solid face tags {sorted(ftags)} != history {want_f}")
            if sorted(t for t in etags if t is not None) != want_e:
                probs.append(f"solid edge tags {sorted(etags)} != history {want_e}")
        # frames per face pid
        frame_of: Dict[int, tuple] = {}
        loop_of: Dict[int, dict] = {}
        for f in faces:
            fv = f.get("value") or {}
            fp = f.get("pid")
            sv = ((fv.get("m_pSurf") or {}).get("value") or {})
            if sv.get("m_origin") and sv.get("m_xVec") and sv.get("m_yVec"):
                frame_of[fp] = (_v(sv["m_origin"]), _v(sv["m_xVec"]), _v(sv["m_yVec"]))
            lp = fv.get("m_pFirstLoop") or {}
            lv = lp.get("value") or {}
            loop_of[fp] = lp
            if not lv:
                probs.append(f"face pid {fp}: no EdgeLoop")
                continue
            wr_ok(lv.get("m_pFace"), ("Face",), f"face {fp} loop.m_pFace", allow_zero=False)
            if isinstance(lv.get("m_pFace"), dict) and lv["m_pFace"].get("weakref") != fp:
                probs.append(f"face pid {fp}: loop.m_pFace -> {lv['m_pFace'].get('weakref')} != {fp}")
            wr_ok(lv.get("m_next"), ("Edge",), f"face {fp} loop.m_next", allow_zero=False)
            wr_ok(lv.get("m_prev"), ("Edge",), f"face {fp} loop.m_prev", allow_zero=False)
            fill = fv.get("m_pGFilling")
            if isinstance(fill, dict) and fill.get("value"):
                wr_ok(fill["value"].get("m_pGFace"), ("Face",), f"face {fp} filling.m_pGFace",
                      allow_zero=False)
                if isinstance(fill["value"].get("m_pGFace"), dict) and \
                        fill["value"]["m_pGFace"].get("weakref") != fp:
                    probs.append(f"face pid {fp}: filling.m_pGFace mismatch")
        # edges: faces / links / uv consistency
        edge_by_pid: Dict[int, dict] = {}
        for e in edges:
            ev = e.get("value") or {}
            ep = e.get("pid")
            edge_by_pid[ep] = ev
            pf = ev.get("m_pFace") or [{}, {}]
            for si in range(2):
                wr_ok(pf[si] if si < len(pf) else {}, ("Face",), f"edge {ep} m_pFace[{si}]",
                      allow_zero=False)
                for arr in ("m_next", "m_prev"):
                    a = ev.get(arr) or [{}, {}]
                    wr_ok(a[si] if si < len(a) else {}, ("Edge", "EdgeLoop"),
                          f"edge {ep} {arr}[{si}]", allow_zero=False)
            # uv <-> 3D consistency between the two face frames
            fa = (pf[0] if len(pf) > 0 else {}).get("weakref")
            fb = (pf[1] if len(pf) > 1 else {}).get("weakref")
            pts = ev.get("m_firstAndLastEdgePnts") or []
            if fa in frame_of and fb in frame_of and len(pts) == 2:
                for which, pt in enumerate(pts):
                    uv = pt.get("uv") if isinstance(pt, dict) else None
                    if not uv or len(uv) != 2:
                        probs.append(f"edge {ep} point {which}: malformed uv {pt}")
                        continue
                    pa = _from_uv(frame_of[fa], uv[0])
                    pb = _from_uv(frame_of[fb], uv[1])
                    if _norm(_sub(pa, pb)) > 1e-6:
                        probs.append(f"edge pid {ep} point {which}: face frames disagree "
                                     f"|{[round(t, 6) for t in pa]} - "
                                     f"{[round(t, 6) for t in pb]}| = {_norm(_sub(pa, pb)):.2e}")
        # loop closure: 4 edges per face, chained via the face's slot
        for f in faces:
            fp = f.get("pid")
            lp = loop_of.get(fp) or {}
            lv = lp.get("value") or {}
            lpid = lp.get("pid")
            if not lv:
                continue
            cur = (lv.get("m_next") or {}).get("weakref")
            seen = []
            guard = 0
            while cur in edge_by_pid and guard < 16:
                if cur in seen:
                    probs.append(f"face pid {fp}: loop revisits edge {cur}")
                    break
                seen.append(cur)
                ev = edge_by_pid[cur]
                pf = [w.get("weakref") for w in (ev.get("m_pFace") or [])]
                if fp not in pf:
                    probs.append(f"face pid {fp}: loop edge {cur} not adjacent to it {pf}")
                    break
                slot = pf.index(fp)
                nxt = (ev.get("m_next") or [{}, {}])[slot].get("weakref")
                cur = nxt
                guard += 1
            if cur != lpid:
                probs.append(f"face pid {fp}: loop chain did not return to loop {lpid} "
                             f"(ended at {cur}, edges {seen})")
            elif len(seen) != 4:
                probs.append(f"face pid {fp}: loop has {len(seen)} edges, expected 4")
    # --- the GGroups (ref planes) -----------------------------------------
    for g in groups:
        gv = g.get("value") or {}
        inner = gv.get("m_subNodes") or []
        if len(inner) != 1 or (inner[0].get("ptr_class") != "Geometry"):
            probs.append(f"GGroup pid {g.get('pid')}: expected 1 inner Geometry")
            continue
        iv = inner[0].get("value") or {}
        if (len(iv.get("m_pFaces") or []), len(iv.get("m_pEdges") or [])) != (1, 4):
            probs.append(f"GGroup pid {g.get('pid')}: ref plane is not 1 face / 4 edges")
    # --- bbox contains every plane origin -------------------------------
    bb = rep.get("m_bBox") or []
    if len(bb) == 2 and solids:
        s = solids[0].get("value") or {}
        for f in s.get("m_pFaces") or []:
            sv = ((f.get("value") or {}).get("m_pSurf") or {}).get("value") or {}
            o = sv.get("m_origin")
            if o and any((o[k] < bb[0][k] - 1e-6) or (o[k] > bb[1][k] + 1e-6) for k in range(3)):
                probs.append(f"face pid {f.get('pid')} origin {o} outside bBox {bb}")
    return probs


def _from_uv(frame, uv) -> List[float]:
    o, x, y = frame
    return _add(_add(o, _mul(x, float(uv[0]))), _mul(y, float(uv[1])))


def rep_summary(rep: dict) -> dict:
    """Small human-readable summary of a rep (for reports / probes.json)."""
    nodes = rep.get("m_subNodes") or []
    solids = [n for n in nodes if n.get("ptr_class") == "Geometry"]
    groups = [n for n in nodes if n.get("ptr_class") == "GGroup"]
    nf = ne = 0
    mats: set = set()
    for s in solids:
        sv = s.get("value") or {}
        nf += len(sv.get("m_pFaces") or [])
        ne += len(sv.get("m_pEdges") or [])
        for f in sv.get("m_pFaces") or []:
            rs = (f.get("value") or {}).get("m_renderStyleId")
            if isinstance(rs, int) and rs != -1:
                mats.add(rs)
    return {"root_category": (rep.get("m_GInfo") or {}).get("m_categoryId"),
            "element_id": rep.get("m_elementId"), "gElemType": rep.get("m_gElemType"),
            "ggroups": len(groups), "solids": len(solids), "solid_faces": nf,
            "solid_edges": ne, "materials": sorted(mats),
            "bBox": rep.get("m_bBox")}


# ===========================================================================
# 8. compare against a native rep (the reproduction proof)
# ===========================================================================

#: leaves ignored when diffing against a native rep: the garbage control
#: command (per-element noise) -- everything else must match
_DIFF_IGNORE_KEYS = frozenset({"m_controlCommand"})


def diff_reps(ours: dict, native: dict, *, eps: float = 1e-6,
              ignore: frozenset = _DIFF_IGNORE_KEYS, limit: int = 200) -> List[str]:
    """Leaf-by-leaf diff of two rep dicts (pids included).  Returns the list
    of differing leaves (EMPTY = identical modulo ``ignore`` and float
    ``eps``)."""
    out: List[str] = []

    def rec(a, b, path):
        if len(out) >= limit:
            return
        if type(a) != type(b):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                    and not isinstance(a, bool) and not isinstance(b, bool):
                if abs(float(a) - float(b)) > eps:
                    out.append(f"{path}: {a!r} vs {b!r}")
                return
            out.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
            return
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b), key=str):
                if k in ignore:
                    continue
                if k not in a:
                    out.append(f"{path}.{k}: only in native")
                    continue
                if k not in b:
                    out.append(f"{path}.{k}: only in ours")
                    continue
                rec(a[k], b[k], f"{path}.{k}")
        elif isinstance(a, list):
            if len(a) != len(b):
                out.append(f"{path}: len {len(a)} vs {len(b)}")
                return
            for i, (x, y) in enumerate(zip(a, b)):
                rec(x, y, f"{path}[{i}]")
        elif isinstance(a, float) or isinstance(b, float):
            if abs(float(a) - float(b)) > eps:
                out.append(f"{path}: {a!r} vs {b!r}")
        else:
            if a != b:
                out.append(f"{path}: {a!r} vs {b!r}")

    rec(ours, native, "")
    return out


def reproduce_native_wall(doc, wall_id: int, native_rep: Optional[dict] = None,
                          **spec_overrides) -> dict:
    """Rebuild a NATIVE wall's rep from its own object and diff it against
    the wall's real seq-103 record -- the proof that the constructor emits
    the native grammar.  Native-only facts we cannot derive (the root
    category style, the ref-plane material, the pattern) are read off the
    native rep and passed in, so the diff measures the CONSTRUCTION.
    Returns {'diff': [...], 'audit': [...], 'spec': ..., 'summary': ...}."""
    if native_rep is None:
        r = doc.decode(wall_id, 103)
        if r is None or not r.value:
            raise WallRenderError(f"wall {wall_id}: no decodable seq-103 rep")
        native_rep = r.value
    ov = dict(spec_overrides)
    ov.setdefault("root_category_id", (native_rep.get("m_GInfo") or {}).get("m_categoryId"))
    # the natives' ref-plane material / solid material / pattern
    nodes = native_rep.get("m_subNodes") or []
    if "refplane_material_id" not in ov:
        for n in nodes:
            if n.get("ptr_class") == "GGroup":
                iv = ((n.get("value") or {}).get("m_subNodes") or [{}])[0].get("value") or {}
                f0 = ((iv.get("m_pFaces") or [{}])[0].get("value") or {})
                ov["refplane_material_id"] = f0.get("m_renderStyleId", INVALID)
                break
    spec = wall_render_spec(doc, wall_id, **ov)
    # solid material / pattern from the native (the doc lookups also work,
    # this makes the diff measure only construction)
    for n in nodes:
        if n.get("ptr_class") == "Geometry":
            fcs = ((n.get("value") or {}).get("m_pFaces") or [])
            f0 = (fcs[0].get("value") or {}) if fcs else {}
            # per-face materials: list order = [cap2, cap1, bottom, finish, top, start]
            def _rs(i):
                if i < len(fcs):
                    v = (fcs[i].get("value") or {}).get("m_renderStyleId")
                    return int(v) if isinstance(v, int) else None
                return None
            thin = _rs(2)
            if thin is not None:
                spec.material_id = thin
            c2, c1 = _rs(0), _rs(1)
            spec.material_cap2 = c2 if (c2 is not None and c2 != spec.material_id) else None
            spec.material_cap1 = c1 if (c1 is not None and c1 != spec.material_id) else None
            fill = ((f0.get("m_pGFilling") or {}).get("value") or {})
            if fill:
                gi = fill.get("m_GInfo") or {}
                if isinstance(gi.get("m_categoryId"), int):
                    spec.fill_category_id = int(gi["m_categoryId"])
                pid = fill.get("m_patternId", INVALID)
                spec.pattern_id = int(pid) if isinstance(pid, int) else INVALID
                if spec.pattern_id != INVALID:
                    spec.pattern_color = int(fill.get("m_fillColor") or 0)
            break
    for n in nodes:
        if n.get("ptr_class") == "GGroup":
            gi = (n.get("value") or {}).get("m_GInfo") or {}
            if isinstance(gi.get("m_categoryId"), int):
                spec.refplane_category_id = int(gi["m_categoryId"])
            break
    tv = (native_rep.get("m_subNodes") or [])
    for n in tv:
        if n.get("ptr_class") == "Geometry":
            tec = ((n.get("value") or {}).get("m_tessEpsCntrl") or {})
            if isinstance(tec.get("m_TessEpsCntrlVersion"), int):
                spec.tess_version = int(tec["m_TessEpsCntrlVersion"])
            break
    ours = build_wall_gelement(spec)
    return {"diff": diff_reps(ours, native_rep), "audit": audit_wall_rep(ours, spec=spec),
            "spec": spec, "ours": ours, "summary": rep_summary(ours)}


# ===========================================================================
# 9. normalize the wall object's geometry bookkeeping to match the rep
# ===========================================================================

def normalize_geometry_history(obj: dict, spec: WallRenderSpec, *,
                               keep_tweak_steps: bool = False,
                               clear_joined_flag: bool = True) -> Dict[str, Any]:
    """Rewrite the wall's seq-102 geometry BOOKKEEPING to the canonical
    UNJOINED standalone-wall state matching the baked rep [the rme 573386
    shape; the trimmed step lists are the state the LOAD-certified
    'unjoin' clones carry]:

    * ``m_geomSteps``: non-BRep [WallRefPlanesGStep], form [BaseWallGStep],
      adjust [VerticalExtensionOfLayersGStep], cut-out / post-cut-out /
      tweak lists emptied (join / split-face steps of the cloned specimen
      dropped -- their tags are NOT in the rep), snapshots nulled, id
      counter = max step id + 1, the 'joined' flag bit cleared.
    * ``m_pGeomTable``: rebuilt to exactly the rep's tags -- ref-step
      generator for tags 0..B-1, the BaseWallGStep for the 18 box tags.
    * ``m_cellList``: CoverSettingsCell concealed faces cleared (a joined
      specimen names its join faces there).
    Returns a change log.  Mutates ``obj`` in place.
    """
    log: Dict[str, Any] = {}
    gsl = _val(obj.get("m_geomSteps"))
    if not gsl:
        log["skipped"] = "no GeomStepList"
        return log
    ref_step = None
    for s in gsl.get("m_nonBRepGList") or []:
        if s.get("ptr_class") == "WallRefPlanesGStep":
            ref_step = s
            break
    base_step = None
    for s in gsl.get("m_bRepFormGList") or []:
        if s.get("ptr_class") == "BaseWallGStep":
            base_step = s
            break
    vert_step = None
    for s in gsl.get("m_bRepAdjustGList") or []:
        if s.get("ptr_class") == "VerticalExtensionOfLayersGStep":
            vert_step = s
            break
    dropped = []
    for lst_name in ("m_nonBRepGList", "m_bRepFormGList", "m_bRepAdjustGList",
                     "m_bRepCutOutGList", "m_bRepPostCutOutGList", "m_bRepTweakGList"):
        for s in gsl.get(lst_name) or []:
            keep = s in (ref_step, base_step, vert_step)
            if lst_name == "m_bRepTweakGList" and keep_tweak_steps:
                keep = True
            if not keep:
                dropped.append(s.get("ptr_class"))
    gsl["m_nonBRepGList"] = [ref_step] if ref_step is not None else []
    gsl["m_bRepFormGList"] = [base_step] if base_step is not None else []
    gsl["m_bRepAdjustGList"] = [vert_step] if vert_step is not None else []
    gsl["m_bRepCutOutGList"] = []
    gsl["m_bRepPostCutOutGList"] = []
    if keep_tweak_steps:
        for s in gsl.get("m_bRepTweakGList") or []:
            sv = _val(s)
            if s.get("ptr_class") == "WallJoinTweakGStep":
                sv["m_affectedEdgesTags"] = []
                sv["m_idGeomJoined"] = []
                sv["m_healingParents"] = []
                sv["m_edgeHistTable"] = []
    else:
        gsl["m_bRepTweakGList"] = []
    log["steps_dropped"] = dropped
    nulled = []
    for k in ("m_bRepFormSnapshot", "m_bRepAdjustSnapshot",
              "m_bRepCutOutSnapshot", "m_bRepPostCutOutSnapshot"):
        if gsl.get(k) is not None:
            gsl[k] = None
            nulled.append(k)
    log["snapshots_nulled"] = nulled
    # step id counter = max present step id + 1
    ids = []
    for lst_name in ("m_nonBRepGList", "m_bRepFormGList", "m_bRepAdjustGList", "m_bRepTweakGList"):
        for s in gsl.get(lst_name) or []:
            mid = _val(s).get("m_id")
            if isinstance(mid, int):
                ids.append(mid)
    old_counter = gsl.get("m_idCounter")
    gsl["m_idCounter"] = (max(ids) + 1) if ids else old_counter
    log["idCounter"] = [old_counter, gsl["m_idCounter"]]
    if clear_joined_flag and isinstance(gsl.get("m_flags"), int):
        old = gsl["m_flags"]
        gsl["m_flags"] = old & ~0x2          # 11 (joined rst) -> 9 (unjoined rme) [V]
        log["gsl_flags"] = [old, gsl["m_flags"]]
    # --- geom table: tags 0..B-1 -> ref step, box tags -> base step -------
    gt_holder = obj.get("m_pGeomTable")
    gtv = _val(gt_holder)
    ref_gen = _val(ref_step).get("m_id", 3) if ref_step is not None else 3
    base_gen = _val(base_step).get("m_id", 1) if base_step is not None else 1
    ref_tags = [rp.tag for rp in spec.ref_planes]
    n_ref = (max(ref_tags) + 1) if ref_tags else 0     # tag 0 = the location curve
    box_tags = sorted(set(spec.face_tags.values()) | set(spec.edge_tags.values()))
    max_tag = max([n_ref - 1] + box_tags) if box_tags else n_ref - 1
    table = []
    for t in range(0, max_tag + 1):
        gen = ref_gen if t < n_ref else (base_gen if t in box_tags else base_gen)
        table.append({"m_geomGeneratorId": int(gen)})
    if gtv:
        old_len = len(gtv.get("m_table") or [])
        gtv["m_table"] = table
        log["geom_table"] = [old_len, len(table)]
    else:
        gt = blank_object("GeomTable")
        gt["m_table"] = table
        obj["m_pGeomTable"] = _ptr("GeomTable", gt)
        log["geom_table"] = [0, len(table)]
    # --- cover settings: no concealed (join) faces --------------------------
    cells = _val(obj.get("m_cellList")).get("m_cells") or []
    for c in cells:
        cv = _val(c)
        if c.get("ptr_class") == "CoverSettingsCell":
            if cv.get("m_concealedFaces"):
                log["concealed_faces_cleared"] = list(cv["m_concealedFaces"])
                cv["m_concealedFaces"] = []
    return log


# ===========================================================================
# 10. the bake APIs
# ===========================================================================

def bake_planned_wall(doc, el, *, normalize: bool = True,
                      root_category_id: Optional[int] = None,
                      material_id: Optional[int] = None,
                      refplane_material_id: Optional[int] = None,
                      with_ref_planes: bool = True,
                      with_fillings: bool = True) -> Dict[str, Any]:
    """CREATE-TIME bake: for a planned ``rvt.mutate.NewElement`` wall,
    build the baked rep, install it as ``el.rep`` (so ``Document.serialize``
    / ``commit_new_elements`` emit a GElement instead of the SerializedDummy)
    and (``normalize``) rewrite the object's geometry bookkeeping to match.
    Returns {'spec', 'audit', 'summary', 'history_log'}."""
    spec = wall_render_spec(doc, el, root_category_id=root_category_id,
                            material_id=material_id,
                            refplane_material_id=refplane_material_id,
                            with_ref_planes=with_ref_planes,
                            with_fillings=with_fillings)
    rep = build_wall_gelement(spec)
    audit = audit_wall_rep(rep, spec=spec)
    if audit:
        raise WallRenderError(f"constructed rep failed self-audit: {audit[:5]}")
    el.rep = rep
    hist = normalize_geometry_history(el.obj, spec) if normalize else {}
    if hasattr(el, "notes") and isinstance(el.notes, list):
        el.notes.append("seq103 = BAKED GElement (rvt.render.wallgeom): 4 ref-plane GGroups + "
                        "6-face/12-edge BaseWallGStep box in the native wall grammar; "
                        "geometry-history bookkeeping normalized to the canonical "
                        "unjoined state" if normalize else
                        "seq103 = BAKED GElement (rvt.render.wallgeom)")
    return {"spec": spec, "audit": audit, "summary": rep_summary(rep), "history_log": hist}


def bake_wall_geometry(src_rvt: str, out_rvt: str, wall_ids: Optional[Sequence[int]] = None,
                       *, normalize: bool = True,
                       root_category_id: Optional[int] = None,
                       material_id: Optional[int] = None,
                       refplane_material_id: Optional[int] = None,
                       with_ref_planes: bool = True,
                       with_fillings: bool = True,
                       verify: bool = True, diff: bool = True) -> Dict[str, Any]:
    """EXISTING-FILE bake: replace the seq-103 (and, with ``normalize``, the
    seq-102) records of created walls IN PLACE and write ``out_rvt``.

    Uses ``rvt.regadd.substitute_elements`` -- the certified in-place
    mechanics: same ids, same ElemTable rows, same record positions,
    Global/Latest byte-identical; the seq-103 record grows from the 2-byte
    SerializedDummy to the GElement (unit 0 is re-blocked by the certified
    re-blocker) and the validator + stream diff run on the result.
    ``wall_ids`` defaults to every host-document SWall of ``src_rvt``.
    Returns a JSON-able report {walls: [...], substitute: {...}}.
    """
    from ..mutate import Document
    from ..regadd import substitute_elements
    doc = Document.from_file(src_rvt)
    ids = list(wall_ids) if wall_ids else doc.ids_of_class("SWall", host_only=True)
    if not ids:
        raise WallRenderError(f"{src_rvt}: no SWall to bake")
    records_by_id: Dict[int, Any] = {}
    walls_report = []
    for wid in ids:
        obj = copy.deepcopy(doc.value(wid))
        if not isinstance(obj, dict):
            raise WallRenderError(f"{src_rvt}: wall {wid} object not decodable")
        spec = wall_render_spec(doc, obj, elem_id=wid,
                                root_category_id=root_category_id,
                                material_id=material_id,
                                refplane_material_id=refplane_material_id,
                                with_ref_planes=with_ref_planes,
                                with_fillings=with_fillings)
        rep = build_wall_gelement(spec)
        audit = audit_wall_rep(rep, spec=spec)
        if audit:
            raise WallRenderError(f"wall {wid}: constructed rep failed self-audit: {audit[:5]}")
        hist = normalize_geometry_history(obj, spec) if normalize else {}
        entry: Dict[str, Any] = {103: (CLASS_GELEMENT, rep)}
        if normalize:
            entry[102] = (CLASS_SWALL, obj)
        records_by_id[int(wid)] = entry
        walls_report.append({"elem_id": int(wid), "spec": spec.to_json(),
                             "rep": rep_summary(rep), "history_log": hist,
                             "warnings": spec.warnings, "notes": spec.notes})
    seqs = (102, 103) if normalize else (103,)
    rep = substitute_elements(src_rvt, out_rvt, records_by_id, seqs=seqs,
                              null=False, keep_row=True, verify=verify, diff=diff)
    return {"src": src_rvt, "out": out_rvt, "walls": walls_report,
            "substitute": rep.to_json() if hasattr(rep, "to_json") else str(rep)}


# ===========================================================================
# 11. render-carriage read-back (via the archaeology stream's inspector)
# ===========================================================================

def render_readback(path: str, wall_ids: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    """Decode a written file and report each wall's rep through
    ``rvt.render.inspect`` (the archaeology stream's carriage inspector)
    when importable, plus our own decode+audit of the GElement.  A wall
    passes when its rep is a GElement with a 6-face solid and the audit is
    clean."""
    from ..mutate import Document
    doc = Document.from_file(path)
    ids = list(wall_ids) if wall_ids else doc.ids_of_class("SWall", host_only=True)
    out: Dict[str, Any] = {"file": path, "walls": [], "all_baked": True}
    insp = None
    try:                                   # optional: the sibling stream's lens
        from . import inspect as _insp     # noqa: WPS433
        insp = _insp
    except Exception:                      # pragma: no cover
        insp = None
    for wid in ids:
        rec103 = doc.record(wid, 103)
        cls = doc.dec.class_name(rec103.class_id) if rec103 else None
        entry: Dict[str, Any] = {"elem_id": int(wid), "rep_class": cls,
                                 "rep_bytes": int(rec103.body_size) if rec103 else 0}
        if cls == "GElement":
            dec = doc.decode(wid, 103)
            rep = dec.value if dec else {}
            entry["decode_clean"] = bool(dec and dec.clean)
            entry["audit"] = audit_wall_rep(rep) if rep else ["no rep"]
            entry["summary"] = rep_summary(rep) if rep else {}
        else:
            entry["decode_clean"] = None
            entry["audit"] = [f"rep is {cls}, not a GElement (nothing baked)"]
        if insp is not None:
            try:
                row = insp.inspect_element(doc, wid)
                entry["inspect"] = {"kind": row.kind, "has_baked_geometry": row.has_baked_geometry,
                                    "n_faces": row.n_faces, "n_edges": row.n_edges,
                                    "drawable_3d": row.drawable_3d}
            except Exception as e:                                 # pragma: no cover
                entry["inspect"] = {"error": f"{type(e).__name__}: {e}"}
        ok = (cls == "GElement" and entry.get("decode_clean") and not entry["audit"])
        entry["baked_ok"] = bool(ok)
        out["all_baked"] = out["all_baked"] and bool(ok)
        out["walls"].append(entry)
    return out


# ===========================================================================
# 12. probe pipeline  (the ifc-room walls, baked, on the certified base)
# ===========================================================================

#: The Walls-category projection GStyleElem id of the rst lineage (element
#: 30 in rst / R5 -- the row every native wall rep names as its root
#: m_GInfo.m_categoryId).  It is one of the catalog rows the R9->ZA_deep
#: reductions GC'd away (no walls in the model), so on ZA_deep it DANGLES
#: until the genesis ADD-cat rung restores the Walls category rows at
#: their lineage ids.  We name it deliberately (forward-compatible with the
#: ADD-cat rung; the R5/R9 dangling-tolerance verdicts show dangling ids are
#: reader-tolerated at LOAD) -- the alternative -1 is available via the
#: ``root_category_id`` argument.
LINEAGE_WALLS_GSTYLE_ID = 30

DEFAULT_BASE = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a", "ZA_deep.rvt")
DEFAULT_SPECIMEN_SRC = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
DEFAULT_INTENT = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.intent.json")
DEFAULT_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
RENDER_DIR = os.path.join(ROOT, "experiments", "ifc_room", "render")
DIAG_HOST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")


def _relp(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT)
    except Exception:
        return p


def _md5(path: str) -> str:
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_ifc_intent_tool():
    """Import tools/ifc_intent.py as a module (IMPORTED, never edited) for
    its SpecimenSet + wall clean-up + level/type pickers."""
    import importlib.util
    path = os.path.join(ROOT, "tools", "ifc_intent.py")
    spec = importlib.util.spec_from_file_location("_ifc_intent_tool", path)
    mod = importlib.util.module_from_spec(spec)                    # type: ignore
    sys.modules["_ifc_intent_tool"] = mod
    assert spec and spec.loader
    spec.loader.exec_module(mod)                                   # type: ignore
    return mod


def _room_wall_lines(intent_path: str = DEFAULT_INTENT) -> List[dict]:
    """The room's wall centerlines (metres -> feet) from the resolved intent
    (falls back to resolving the IFC when the intent JSON is absent)."""
    FT = 1.0 / 0.3048
    walls: List[dict] = []
    if os.path.exists(intent_path):
        with open(intent_path) as fh:
            data = json.load(fh)
        room = (data.get("model") or data).get("room") or data.get("room") or {}
        for w in room.get("walls") or []:
            p0 = w.get("p0_m") or w.get("p0") or (w.get("centerline") or {}).get("p0")
            p1 = w.get("p1_m") or w.get("p1") or (w.get("centerline") or {}).get("p1")
            h = w.get("height_m") or w.get("height") or 3.66
            if p0 and p1:
                walls.append({"id": w.get("wall_id") or w.get("id") or f"W{len(walls) + 1}",
                              "p0_ft": [float(p0[0]) * FT, float(p0[1]) * FT],
                              "p1_ft": [float(p1[0]) * FT, float(p1[1]) * FT],
                              "height_ft": float(h) * FT})
    if walls:
        return walls
    # fall back to the intent resolver on the IFC
    from ..ifc import intent as I
    model = I.resolve_intent(DEFAULT_IFC)
    for w in model.room.walls:
        walls.append({"id": w.wall_id, "p0_ft": [w.p0_m[0] * FT, w.p0_m[1] * FT],
                      "p1_ft": [w.p1_m[0] * FT, w.p1_m[1] * FT],
                      "height_ft": w.height_m * FT})
    return walls


def build_walls_file(base_rvt: str, out_path: str, wall_lines: Sequence[dict], *,
                     specimen_src: str = DEFAULT_SPECIMEN_SRC,
                     bake: bool = True, wall_mode: str = "unjoin",
                     normalize: bool = True,
                     root_category_id: Optional[int] = None,
                     with_ref_planes: bool = True,
                     with_fillings: bool = True,
                     level_id: Optional[int] = None,
                     wall_type_id: Optional[int] = None) -> Dict[str, Any]:
    """Create walls on ``base_rvt`` (the ifc-room pipeline's stage W: R5
    specimen scaffolding + add_wall + clone clean-up) and, with ``bake``,
    BAKE each wall's rep before the commit.  Writes ``out_path``.
    ``wall_lines`` = [{p0_ft, p1_ft, height_ft}]; ``wall_type_id``
    overrides the base's default wall type (default: the base's first
    BasicWallType, as the ifc-room stage does).  Returns a report."""
    from ..mutate import Document
    from ..commit import commit_new_elements, verify_written
    tool = _load_ifc_intent_tool()
    t0 = time.time()
    rep: Dict[str, Any] = {"base": _relp(base_rvt), "out": _relp(out_path),
                           "specimen_source": _relp(specimen_src), "bake": bake,
                           "wall_mode": wall_mode, "normalize": normalize, "walls": []}
    doc = Document.from_file(base_rvt)
    specimens = tool.SpecimenSet(specimen_src)
    rep["specimens"] = specimens.inject_into(doc)
    wt = int(wall_type_id) if wall_type_id is not None else tool._wall_type_of_base(doc)
    if wt is None or (wall_type_id is not None and not doc.exists(wt)):
        raise WallRenderError(f"{base_rvt}: wall type {wt} not available")
    lvl = level_id if level_id is not None else tool._pick_level(doc, 0.0)
    rep.update({"wall_type": wt, "level": lvl, "wall_specimen": specimens.wall_id})
    els = []
    for w in wall_lines:
        el = doc.add_wall(lvl, wt, tuple(w["p0_ft"]), tuple(w["p1_ft"]),
                          height=float(w["height_ft"]), template_id=specimens.wall_id)
        clean = tool._clean_wall_clone(el, doc, specimens.wall_id, mode=wall_mode)
        entry: Dict[str, Any] = {"elem_id": el.elem_id, "p0_ft": w["p0_ft"],
                                 "p1_ft": w["p1_ft"], "height_ft": w["height_ft"],
                                 "clone_cleanup": clean,
                                 "dangling_refs": doc.check_references(el)[:12]}
        if bake:
            b = bake_planned_wall(doc, el, normalize=normalize,
                                  root_category_id=root_category_id,
                                  with_ref_planes=with_ref_planes,
                                  with_fillings=with_fillings)
            entry["baked"] = {"summary": b["summary"], "history_log": b["history_log"],
                              "warnings": b["spec"].warnings, "notes": b["spec"].notes,
                              "root_category_id": b["spec"].root_category_id,
                              "material_id": b["spec"].material_id,
                              "refplane_category_id": b["spec"].refplane_category_id,
                              "refplane_material_id": b["spec"].refplane_material_id}
        els.append(el)
        rep["walls"].append(entry)
    records, plans = [], []
    for el in els:
        recs = doc.serialize(el)
        if recs is None:
            raise WallRenderError("rvt.encode unavailable")
        records.append(dict(recs))
        plans.append(el.elemrec)
    crep = commit_new_elements(base_rvt, out_path, records, plans)
    ids = [p.elem_id for p in plans]
    ver = verify_written(out_path, ids)
    rep["new_ids"] = ids
    rep["commit"] = {"elemtable_after": crep.elemtable_count_after,
                     "watermark_after": crep.watermark_after,
                     "bytes_added": dict(crep.per_seq_bytes_added)}
    rep["verify_written"] = ver
    rep["structurally_valid"] = bool(all(
        all(x.get("clean") for x in ver["new_ids_found"][s].values()) for s in ver["new_ids_found"]))
    rep["seconds"] = round(time.time() - t0, 1)
    rep["md5"] = _md5(out_path)
    return rep


def _validate(path: str) -> Dict[str, Any]:
    """Certified project-mode arbiter (tools/rvt_validate.py == rvt.validate)."""
    try:
        from ..validate import validate_file
        rep = validate_file(path)
        return {"verdict": "VALID" if rep.ok else "INVALID", "ok": bool(rep.ok),
                "errors": len(rep.errors), "warnings": len(rep.warnings),
                "first_errors": [str(f.to_json()) for f in rep.errors[:5]],
                "stats": {k: rep.stats.get(k) for k in ("elements_decoded", "decode_failures",
                                                          "refs_checked") if k in rep.stats}}
    except Exception as e:                                                    # pragma: no cover
        return {"verdict": None, "errors": None, "ok": None, "error": f"{type(e).__name__}: {e}"}


def build_render_probes(out_dir: str = RENDER_DIR, *,
                        base_rvt: str = DEFAULT_BASE,
                        specimen_src: str = DEFAULT_SPECIMEN_SRC,
                        with_diagnostic_host: bool = True) -> Dict[str, Any]:
    """Build the RENDER probe set + probes.json in ``out_dir``:

    * ``CTRL_ZA_deep_render.rvt`` -- byte-identical copy of the certified base.
    * ``walls_baked.rvt`` -- the room's four walls (unjoined) with BAKED reps
      and canonical unjoined bookkeeping (create-time bake).
    * ``walls_baked_reponly.rvt`` -- the room's walls with the reps baked
      but the cloned geometry-history bookkeeping left untouched (variable
      isolation: rep-only).
    * ``wall_baked_min.rvt`` -- the certified base + ONE baked wall (the
      cleanest render test).
    * ``walls_only_dummy.rvt`` -- the same four walls WITHOUT baking (the
      SerializedDummy state = the LOAD-certified control for the wall layer).
    * ``diag_rst_wall_baked.rvt`` (diagnostic, base = the rst SAMPLE, which
      carries the Walls-category GStyle row 30 our lineage lacks) -- one
      baked wall on the untouched sample, to separate 'our baked geometry'
      from 'the genesis base lacks the Walls category style'.
    Every probe declares the certified base it descends from; the manifest
    (probes.json) is checked with tools/probe_batch.py.
    """
    import shutil
    os.makedirs(out_dir, exist_ok=True)
    report: Dict[str, Any] = {"stream": "render-emit", "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                              "base": _relp(base_rvt), "specimen_source": _relp(specimen_src),
                              "files": {}}
    walls = _room_wall_lines()
    report["room_walls"] = walls

    ctrl = os.path.join(out_dir, "CTRL_ZA_deep_render.rvt")
    shutil.copyfile(base_rvt, ctrl)
    report["files"]["CTRL_ZA_deep_render.rvt"] = {"kind": "control", "md5": _md5(ctrl),
                                                    "identical_to": _relp(base_rvt)}

    root_cat = LINEAGE_WALLS_GSTYLE_ID
    report["root_category_id"] = root_cat

    f_dummy = os.path.join(out_dir, "walls_only_dummy.rvt")
    r_dummy = build_walls_file(base_rvt, f_dummy, walls, specimen_src=specimen_src,
                               bake=False, wall_mode="unjoin", normalize=False)
    report["files"]["walls_only_dummy.rvt"] = _file_entry(f_dummy, r_dummy, base_rvt,
                                                          "the room's 4 walls, UNBAKED "
                                                          "(SerializedDummy reps) = the LOAD-"
                                                          "certified wall layer, this session's build")

    f_baked = os.path.join(out_dir, "walls_baked.rvt")
    r_baked = build_walls_file(base_rvt, f_baked, walls, specimen_src=specimen_src,
                               bake=True, wall_mode="unjoin", normalize=True,
                               root_category_id=root_cat)
    report["files"]["walls_baked.rvt"] = _file_entry(f_baked, r_baked, base_rvt,
                                                     "the room's 4 walls with BAKED GElement reps "
                                                     "(4 ref-plane GGroups + 6-face box) and "
                                                     "canonical unjoined geometry bookkeeping")

    f_rep = os.path.join(out_dir, "walls_baked_reponly.rvt")
    r_rep = build_walls_file(base_rvt, f_rep, walls, specimen_src=specimen_src,
                             bake=True, wall_mode="unjoin", normalize=False,
                             root_category_id=root_cat)
    report["files"]["walls_baked_reponly.rvt"] = _file_entry(
        f_rep, r_rep, base_rvt,
        "the room's 4 walls with BAKED reps, cloned geometry-history bookkeeping "
        "UNTOUCHED (variable isolation vs walls_baked: only the seq-103 rep differs "
        "from walls_only_dummy)")

    f_min = os.path.join(out_dir, "wall_baked_min.rvt")
    one = [{"id": "W_min", "p0_ft": [-10.0, 0.0], "p1_ft": [10.0, 0.0],
            "height_ft": 12.007874015748031}]
    r_min = build_walls_file(base_rvt, f_min, one, specimen_src=specimen_src,
                             bake=True, wall_mode="unjoin", normalize=True,
                             root_category_id=root_cat)
    report["files"]["wall_baked_min.rvt"] = _file_entry(f_min, r_min, base_rvt,
                                                        "the certified base + ONE baked wall "
                                                        "(20 ft x 3.66 m at the origin) = the "
                                                        "cleanest render test")

    f_ncat = os.path.join(out_dir, "wall_baked_min_catneg.rvt")
    r_ncat = build_walls_file(base_rvt, f_ncat, one, specimen_src=specimen_src,
                              bake=True, wall_mode="unjoin", normalize=True,
                              root_category_id=INVALID)
    report["files"]["wall_baked_min_catneg.rvt"] = _file_entry(
        f_ncat, r_ncat, base_rvt,
        "the same single baked wall with the rep ROOT category = -1 (no category "
        "style) instead of the dangling Walls GStyle id 30 -- the root-category "
        "A/B for the extractor")

    if with_diagnostic_host and os.path.exists(DIAG_HOST):
        try:
            f_diag = os.path.join(out_dir, "diag_rst_wall_baked.rvt")
            # type the diagnostic wall with the specimen's OWN wall type
            # (rst 600634 'CL_W1', the 280 mm single-layer type whose ref
            # planes the clone carries) so the wall is native-typed
            from ..mutate import Document as _D
            _rst = _D.from_file(DIAG_HOST)
            diag_wt = 600634 if _rst.exists(600634) else None
            del _rst
            r_diag = build_walls_file(DIAG_HOST, f_diag, one, specimen_src=DIAG_HOST,
                                      bake=True, wall_mode="unjoin", normalize=True,
                                      wall_type_id=diag_wt)
            report["files"]["diag_rst_wall_baked.rvt"] = _file_entry(
                f_diag, r_diag, DIAG_HOST,
                "DIAGNOSTIC: one baked wall (our constructor, R5-lineage specimen = rst's "
                "own wall type 600634) on the untouched rst SAMPLE -- which HAS the Walls-"
                "category GStyle row 30, the Default material 24 and native walls; separates "
                "'our baked geometry is wrong' from 'the genesis base lacks the Walls "
                "category catalog rows'")
        except Exception as e:
            report["files"]["diag_rst_wall_baked.rvt"] = {"error": f"{type(e).__name__}: {e}"}

    manifest = _write_probes_manifest(out_dir, base_rvt, report)
    report["probes_json"] = _relp(manifest)
    with open(os.path.join(out_dir, "render_build.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    return report


def _file_entry(path: str, build_report: Dict[str, Any], base: str, what: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"kind": "probe", "what": what, "md5": _md5(path),
                             "base": _relp(base), "build": build_report}
    entry["validate"] = _validate(path)
    try:
        # judge only the walls WE created (a sample host carries native
        # joined walls whose reps legitimately have more than 6 faces)
        entry["render_readback"] = render_readback(path, wall_ids=build_report.get("new_ids"))
    except Exception as e:                                                   # pragma: no cover
        entry["render_readback"] = {"error": f"{type(e).__name__}: {e}"}
    return entry


def _write_probes_manifest(out_dir: str, base_rvt: str, report: Dict[str, Any]) -> str:
    files = report["files"]
    probes = []

    def entry(name, probe_id, tests, if_pass, if_fail, kind="probe", base=None):
        f = files.get(name) or {}
        if "md5" not in f:
            return None
        return {
            "file": _relp(os.path.join(out_dir, name)), "probe": probe_id, "kind": kind,
            "base": base or _relp(base_rvt), "md5": f.get("md5"),
            "validator": (f.get("validate") or {}).get("verdict"),
            "validator_errors": (f.get("validate") or {}).get("errors"),
            "render_readback_all_baked": ((f.get("render_readback") or {}).get("all_baked")
                                          if isinstance(f.get("render_readback"), dict) else None),
            "tests": tests, "if_PASS": if_pass, "if_FAIL": if_fail,
        }
    e = entry("walls_baked.rvt", "REND_walls_baked",
              "the room's four walls with BAKED reps: are the created walls now VISIBLE "
              "in the model tree / 3D (the RENDER gate) and does the file still LOAD?",
              "created walls RENDER on the family-free genesis base -- LOAD is now also "
              "RENDER for the wall layer",
              "read the card + the model tree: 'Design is empty'/no wall nodes with LOAD ok => "
              "the geometry did not draw (root category / material / grammar) -- compare "
              "wall_baked_min and the diagnostic rst-hosted probe; a LOAD failure => bisect "
              "vs walls_baked_reponly (bookkeeping) and walls_only_dummy (the certified state)")
    if e:
        e["render"] = {"gate": "RENDER (model tree contains 4 wall nodes; 3D shows the "
                       "9.2 x 6.2 m room ring)", "load_control": "walls_only_dummy.rvt"}
        probes.append(e)
    e = entry("walls_baked_reponly.rvt", "REND_walls_baked_reponly",
              "same as REND_walls_baked but the cloned geometry-history bookkeeping is "
              "UNTOUCHED -- only the seq-103 rep changed vs walls_only_dummy",
              "the rep alone renders (bookkeeping normalization not required)",
              "if REND_walls_baked passes and this fails: the bookkeeping/rep mismatch "
              "matters to the extractor; if both fail: the rep/grammar or the base")
    if e:
        probes.append(e)
    e = entry("wall_baked_min.rvt", "REND_wall_min",
              "the certified base + ONE baked wall: the cleanest render test",
              "a single created wall renders on ZA_deep",
              "no wall node / 'Design is empty' => our baked geometry or a missing base "
              "prerequisite (the Walls-category GStyle row 30 is absent from ZA_deep -- see "
              "the diagnostic probe); a LOAD failure => the bake path itself")
    if e:
        probes.append(e)
    e = entry("wall_baked_min_catneg.rvt", "REND_wall_min_catneg",
              "the single baked wall with rep ROOT category -1 instead of the dangling "
              "Walls GStyle id 30 (root-category A/B)",
              "the extractor draws a wall rep with no category style -> the root "
              "category is not the gate",
              "if REND_wall_min passes and this fails (or vice versa): the root category "
              "id matters -- keep the winning form")
    if e:
        probes.append(e)
    e = entry("walls_only_dummy.rvt", "REND_walls_dummy_control",
              "the same four walls WITHOUT baking (SerializedDummy reps) -- the wall "
              "layer in its LOAD-certified state, rebuilt this session",
              "LOAD control for the wall layer (must PASS; renders nothing by design)",
              "the wall add path regressed vs verdict #22 -- read before the baked probes",
              kind="control-probe")
    if e:
        probes.append(e)
    d = files.get("diag_rst_wall_baked.rvt")
    if d and "md5" in d:
        e = entry("diag_rst_wall_baked.rvt", "REND_diag_rst",
                  "DIAGNOSTIC on the rst SAMPLE (certified source): one baked wall built "
                  "by the SAME constructor where the Walls-category GStyle (30), the "
                  "Default material (24) and native walls all exist",
                  "our constructor's geometry renders where the category catalog is "
                  "complete => a ZA_deep render failure is the missing Walls category "
                  "rows (the ADD-cat rung), NOT the geometry",
                  "our geometry does not render even on a complete host => the grammar "
                  "(read the card / model tree)", base=_relp(DIAG_HOST))
        if e:
            probes.append(e)
    ctrl = files.get("CTRL_ZA_deep_render.rvt") or {}
    manifest = {
        "stream": "render-emit (genesis-11): BAKED wall geometry so created walls RENDER "
                  "(LOAD is not RENDER -- the cloud extractor draws baked seq-103 geometry only)",
        "base": {"file": _relp(base_rvt),
                 "certification": {"file": _relp(base_rvt),
                                   "proves": "ZA_deep = certified deep genesis rung "
                                             "(ORCHESTRATOR VERDICTS #18: ZA_deep PASS)"},
                 "note": "every ZA_deep-based candidate declares this SAME certified base"},
        "standing_control": {"file": _relp(os.path.join(out_dir, "CTRL_ZA_deep_render.rvt")),
                             "identical_to": _relp(base_rvt), "md5": ctrl.get("md5"),
                             "purpose": "byte-identical copy of the certified base -- read "
                                        "FIRST; a control FAIL voids the round"},
        "read_order": "control FIRST; then walls_only_dummy (the LOAD-certified wall state, "
                      "rebuilt); then wall_baked_min (single baked wall); then walls_baked / "
                      "walls_baked_reponly; the diagnostic rst-hosted probe reads INDEPENDENTLY "
                      "of the ZA_deep set",
        "the_render_gate": "for each baked probe read TWO things: (1) LOAD (translation) "
                           "PASS/FAIL as before, (2) the MODEL TREE / 3D view: do the wall "
                           "elements appear (a rendered element = a browser node under its "
                           "level with an eye toggle)? A LOAD PASS with an empty tree = the "
                           "geometry did not draw.",
        "known_co_blocker": "ZA_deep carries NO Walls-category projection GStyleElem (rst row "
                            "30, one of the GC'd catalog rows; its category catalog HAS the "
                            "rows for Levels(144)/Doors(44)/ElectricalEquipment(124)/Lines(69) "
                            "which DO render). The baked reps reference root category 30 "
                            "(dangling until the ADD-cat rung restores it). The rst-hosted "
                            "diagnostic probe isolates this variable.",
        "reading_the_results": {
            "control FAIL": "oracle/environment problem -- every verdict VOID",
            "dummy control PASS + wall_min renders": "created walls RENDER: the render "
                                                     "track's core question answered YES",
            "wall_min LOAD-PASS but empty": "the geometry did not draw -- if the rst-hosted "
                                            "diagnostic RENDERS, the fix is the ADD-cat rung "
                                            "(Walls GStyle row 30 + friends), not the geometry",
            "diag renders + ZA_deep does not": "the ADD-cat rung is the render blocker",
            "diag does not render": "the constructed grammar -- read the card, compare with "
                                    "the archaeology stream's rvt.render.brep box (a "
                                    "second, independent construction to A/B)",
        },
        "probes": probes,
    }
    path = os.path.join(out_dir, "probes.json")
    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    return path


# ===========================================================================
# 13. fixture I/O (a native wall's records, for the fast reproduction test)
# ===========================================================================

FIXTURE_DIR = os.path.join(RENDER_DIR, "fixtures")


def dump_native_fixture(project: str, wall_id: int, out_path: Optional[str] = None,
                        cache_dir: Optional[str] = None) -> str:
    """Save one native wall's decoded records + its type object + the layer
    materials' ids as a JSON fixture -- a reproduction ORACLE for the fast
    tests (source recorded; the fixture is derived data of a sample wall)."""
    from ..mutate import Document
    doc = Document.load(project, cache_dir=cache_dir)
    v101 = doc.decode(wall_id, 101)
    v102 = doc.decode(wall_id, 102)
    v103 = doc.decode(wall_id, 103)
    if not (v102 and v103 and v102.clean and v103.clean):
        raise WallRenderError(f"{project} {wall_id}: records not cleanly decodable")
    wt = v102.value.get("m_WallAttributesId")
    tobj = doc.value(wt) if wt else None
    cs = _val((tobj or {}).get("m_pCompoundStructure"))
    mats = sorted({int((L or {}).get("m_materialId")) for L in (cs.get("m_layers") or [])
                   if isinstance((L or {}).get("m_materialId"), int) and (L or {}).get("m_materialId") > 0})
    data = {"source": {"project": project, "wall_id": wall_id,
                       "provenance": "decoded records of an Autodesk 2026 SAMPLE wall "
                                     "(rvt corpus); used ONLY as a reproduction oracle "
                                     "for tests/test_render_wallgeom.py"},
            "seq101": v101.value if v101 else None,
            "seq102": v102.value, "seq103": v103.value,
            "type": {"id": wt, "object": tobj, "layer_materials": mats}}
    out_path = out_path or os.path.join(FIXTURE_DIR, f"native_wall_{project}_{wall_id}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=1, default=str)
    return out_path


class _FixtureDoc:
    """A minimal doc facade over a fixture (value/exists/class_of/ids_of_class)
    -- just enough for wall_render_spec's lookups in the tests."""

    def __init__(self, values: Dict[int, dict], classes: Dict[int, str],
                 headers: Optional[Dict[int, dict]] = None):
        self._values = values
        self._classes = classes
        self._headers = headers or {}

    def value(self, eid, seq=102):
        return self._values.get(eid)

    def exists(self, eid):
        return eid in self._values or eid in self._classes

    def class_of(self, eid, seq=102):
        return self._classes.get(eid)

    def ids_of_class(self, name, host_only=True):
        return [i for i, c in self._classes.items() if c == name]

    def decode(self, eid, seq=102):
        if seq == 101 and eid in self._headers:
            class _H:                                        # mimic DecodedObject
                def __init__(self, v):
                    self.value = v
                    self.clean = True
            return _H(self._headers[eid])
        return None


def load_fixture_doc(path: str) -> Tuple["_FixtureDoc", int, dict]:
    """Load a fixture written by :func:`dump_native_fixture` into a doc
    facade.  Returns (doc, wall_id, native_rep)."""
    with open(path) as fh:
        data = json.load(fh)
    wid = int(data["source"]["wall_id"])
    tinfo = data.get("type") or {}
    values = {wid: data["seq102"]}
    classes = {wid: "SWall"}
    tid = tinfo.get("id")
    if isinstance(tid, int) and tinfo.get("object"):
        values[int(tid)] = tinfo["object"]
        classes[int(tid)] = "BasicWallType"
    for m in tinfo.get("layer_materials") or []:
        classes[int(m)] = "MaterialElem"
    headers = {wid: data["seq101"]} if data.get("seq101") else {}
    return _FixtureDoc(values, classes, headers), wid, data["seq103"]


# ===========================================================================
# 14. CLI
# ===========================================================================

def _cli_reproduce(argv: List[str]) -> int:
    project = argv[0] if len(argv) > 0 else "rmebasicsampleproject"
    wall_id = int(argv[1]) if len(argv) > 1 else 573386
    cache = os.environ.get("RVT_SEG_CACHE")
    from ..mutate import Document
    print(f"loading {project} (seq cache {cache!r}) ...")
    doc = Document.load(project, cache_dir=cache)
    r = reproduce_native_wall(doc, wall_id)
    print(f"wall {wall_id} ({project}): reproduction diff = {len(r['diff'])} leaves, "
          f"audit = {len(r['audit'])} problems")
    for d in r["diff"][:60]:
        print("   DIFF ", d)
    for a in r["audit"][:20]:
        print("   AUDIT", a)
    print(json.dumps(r["summary"], indent=1))
    return 0 if not r["diff"] and not r["audit"] else 1


def _cli_bake(argv: List[str]) -> int:
    if len(argv) < 2:
        print("usage: bake IN.rvt OUT.rvt [wall ids...] [--root-cat N] [--no-normalize]")
        return 2
    src, out = argv[0], argv[1]
    root_cat = None
    normalize = True
    ids: List[int] = []
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--root-cat" and i + 1 < len(argv):
            root_cat = int(argv[i + 1]); i += 2
        elif a == "--no-normalize":
            normalize = False; i += 1
        elif a.isdigit():
            ids.append(int(a)); i += 1
        else:
            print(f"unknown arg {a!r}"); return 2
    rep = bake_wall_geometry(src, out, ids or None, normalize=normalize,
                             root_category_id=root_cat)
    print(json.dumps({"out": rep["out"], "walls": [w["elem_id"] for w in rep["walls"]],
                      "substitute_verdict": (rep["substitute"] or {}).get("verdict")
                      if isinstance(rep["substitute"], dict) else None}, indent=1))
    for w in rep["walls"]:
        for msg in w.get("warnings") or []:
            print(f"   wall {w['elem_id']} WARN: {msg}")
    return 0


def _cli_audit(argv: List[str]) -> int:
    if not argv:
        print("usage: audit FILE.rvt")
        return 2
    r = render_readback(argv[0])
    print(json.dumps(r, indent=1, default=str))
    return 0 if r.get("all_baked") else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "reproduce":
        return _cli_reproduce(rest)
    if cmd == "bake":
        return _cli_bake(rest)
    if cmd == "audit":
        return _cli_audit(rest)
    if cmd == "fixture":
        project = rest[0] if rest else "rmebasicsampleproject"
        wid = int(rest[1]) if len(rest) > 1 else 573386
        path = dump_native_fixture(project, wid, cache_dir=os.environ.get("RVT_SEG_CACHE"))
        print(f"wrote fixture -> {path}")
        return 0
    if cmd in ("all", "room", "probes"):
        rep = build_render_probes()
        print(json.dumps({k: (v.get("md5") if isinstance(v, dict) else v)
                          for k, v in rep["files"].items()}, indent=1))
        print(f"probes.json -> {rep['probes_json']}")
        return 0
    print(f"unknown command {cmd!r}; try help")
    return 2


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())

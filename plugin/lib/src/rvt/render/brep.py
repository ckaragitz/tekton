"""rvt.render.brep -- AUTHOR the baked B-rep solid of a straight wall
(the seq-103 ``GElement`` a native wall carries and our created walls
never did).

This is the RENDER prescription of ``docs/writer/baked-geometry.md`` made
executable: ``rvt.mutate.Document.add_wall`` clones a real wall's OBJECT
(seq 102) -- location line, ref-face planes, the ``GeomStepList`` recipe
whose ``BaseWallGStep`` DECLARES a six-face box (6 face tags + 12 edge
tags) -- but writes a ``SerializedDummy`` REP (seq 103), betting on
regeneration the cloud viewer never performs.  A native wall's rep is a
decoded scene graph ``GElement -> Geometry (GBRep)`` whose faces / edges /
loops / planes are the SAME grammar ``rvt.famgen.geometry`` already
authors for family solids (byte-compatible flag constants; see the
calibration table in the doc).  So the wall body -- a box aligned to the
location line -- is built with :func:`rvt.famgen.geometry.solid_box_brep`
and re-tagged / re-materialed to the wall's own history.

Face semantics of ``BaseWallGStep.m_faceHistTable`` (VERIFIED against a
native joined wall's actual face normals; ``u`` = unit line direction,
``n_left = (-u.y, u.x, 0)``)::

    key (1,-1,-1)  LEFT  side, outward normal +n_left, plane at line + n_left*off_left
    key (2,-1,-1)  RIGHT side, outward normal -n_left, plane at line + n_left*off_right
    key (3,0,-1)   START cap at p0, normal -u
    key (3,1,-1)   FAR   cap at p1, normal +u
    key (3,2,-1)   BOTTOM, normal -Z (z = base)
    key (3,3,-1)   TOP,    normal +Z (z = base + height)

``m_isFlipped`` reorders the compound-structure LAYERS (which side is the
exterior finish), NOT the box: the geometry is always line +
n_left*[off_right .. off_left].  Materials: the finish material rides on
the sides / top / bottom and the "Default Wall" (core) material on the two
end caps (native pattern); pass ``-1`` where the base lacks a material.

Public API::

    geom = wall_geometry_from_object(wall_obj, base_z, height)   # from the wall's own seq-102 object
    tags = tags_from_wall_object(wall_obj)                        # BaseWallGStep face/edge tags
    rep  = wall_solid_brep(geom, tags, element_id=id, ...)        # the seq-103 GElement dict
    # then: rvt.regadd.substitute_elements(src, out, {id: {103: (0x89e, rep)}}, seqs=(103,))

The GElement produced is the exact record shape of a native unjoined
wall's rep: root ``GElement`` (bBox / gElemType 3 / elementId) -> ONE main
``Geometry`` solid (6 planar faces, 12 edges) [+ optional single-face
ref-plane sub-graphics under ``GGroup`` nodes, as native walls carry].
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..genesis.types import blank_object, INVALID
from ..famgen.geometry import (
    solid_box_brep, ginfo, plane, REGISTERED_CLASSES,
    _ptr, _weak,
    GELEM_ROOT_FLAGS, GEOMETRY_FLAGS, LOOP_INFO_FLAGS,
    EDGE_INFO_FLAGS, EDGE_FLAGS_FORWARD_IN_A,
)

Vec = Sequence[float]

#: seq-103 class id of GElement (the rep record class we author)
CLASS_GELEMENT = 0x089E

#: Face.m_GInfo.m_flags on native wall solid faces (dominant value over
#: 69 walls / 1,287 faces; identical to famgen's EDGE_INFO_FLAGS) [V]
WALL_FACE_INFO_FLAGS = 557572
#: Face.m_faceFlags_v9 on native wall faces (dominant; == famgen's) [V]
WALL_FACE_FLAGS_V9 = 4
#: GGroup.m_GInfo.m_flags of the four ref-plane sub-graphics (native
#: pattern: two of one kind, one of each other; irrelevant to the solid) [V]
REFPLANE_GROUP_FLAGS = 34111648
#: BaseWallGStep face-history keys (see module docstring) [V]
KEY_LEFT = (1, -1, -1)
KEY_RIGHT = (2, -1, -1)
KEY_START = (3, 0, -1)
KEY_FAR = (3, 1, -1)
KEY_BOTTOM = (3, 2, -1)
KEY_TOP = (3, 3, -1)


# ---------------------------------------------------------------------------
# inputs: the wall's own geometry and history tags, read off its object
# ---------------------------------------------------------------------------

@dataclass
class WallGeometry:
    """A straight wall's box, in feet (the frame add_wall already computes)."""
    p0: List[float]                 # location line start (xy, z ignored)
    p1: List[float]                 # location line end
    base_z: float                   # base elevation (level + base offset)
    height: float                   # unconnected height
    off_left: float                 # left side-face offset along n_left (usually +t/2)
    off_right: float                # right side-face offset along n_left (usually -t/2)

    @property
    def u(self) -> List[float]:
        dx, dy = self.p1[0] - self.p0[0], self.p1[1] - self.p0[1]
        n = math.hypot(dx, dy)
        if n <= 1e-12:
            raise ValueError("degenerate wall: p0 == p1")
        return [dx / n, dy / n, 0.0]

    @property
    def n_left(self) -> List[float]:
        u = self.u
        return [-u[1], u[0], 0.0]

    @property
    def length(self) -> float:
        return math.hypot(self.p1[0] - self.p0[0], self.p1[1] - self.p0[1])

    @property
    def thickness(self) -> float:
        return abs(self.off_left - self.off_right)

    @property
    def top_z(self) -> float:
        return self.base_z + self.height

    def corners(self) -> List[List[float]]:
        """The plan footprint, COUNTER-CLOCKWISE viewed from +z, ordered so
        solid_box_brep's side_i lands on a known wall face:
        V0=p0.right, V1=p1.right, V2=p1.left, V3=p0.left =>
        side_0=RIGHT, side_1=FAR cap, side_2=LEFT, side_3=START cap."""
        n = self.n_left
        lo, hi = min(self.off_right, self.off_left), max(self.off_right, self.off_left)
        def at(p, off):
            return [p[0] + n[0] * off, p[1] + n[1] * off, 0.0]
        return [at(self.p0, lo), at(self.p1, lo), at(self.p1, hi), at(self.p0, hi)]


@dataclass
class WallTags:
    """The stable geometry tags a wall's own ``GeomStepList`` DECLARES
    (``BaseWallGStep`` face / edge history) -- reusing them keeps the rep
    consistent with the object's history + ``m_pGeomTable`` by
    construction (no new tag allocation)."""
    faces: Dict[Tuple[int, int, int], int] = dc_field(default_factory=dict)  # key -> tag
    edges: List[int] = dc_field(default_factory=list)                          # 12 edge tags
    refplanes: List[int] = dc_field(default_factory=list)                      # ref-plane geom tags
    source: str = "fresh"                                                     # 'history' | 'fresh'

    @property
    def complete(self) -> bool:
        return all(k in self.faces for k in (KEY_LEFT, KEY_RIGHT, KEY_START,
                                             KEY_FAR, KEY_BOTTOM, KEY_TOP)) \
            and len(self.edges) >= 12

    @classmethod
    def fresh(cls, base: int = 100) -> "WallTags":
        """Freshly allocated tags (for a wall with no cloned history).  The
        caller must then also emit a matching BaseWallGStep + GeomTable."""
        keys = (KEY_LEFT, KEY_RIGHT, KEY_START, KEY_FAR, KEY_BOTTOM, KEY_TOP)
        t = cls(faces={k: base + i for i, k in enumerate(keys)},
                edges=[base + 6 + i for i in range(12)],
                refplanes=[base + 18 + i for i in range(4)], source="fresh")
        return t


def _unwrap(x):
    if isinstance(x, dict) and "ptr_class" in x:
        return x.get("value") or {}
    return x if isinstance(x, dict) else {}


def tags_from_wall_object(wall_obj: dict) -> WallTags:
    """Read the six face tags / twelve edge tags a (cloned) wall's own
    ``BaseWallGStep`` declares, plus its ``WallRefPlanesGStep`` ref-plane
    tags.  Falls back to :meth:`WallTags.fresh` when the object carries no
    box-shaped history (source = 'fresh')."""
    steps = _unwrap((wall_obj.get("m_geomSteps") or {}))
    tags = WallTags(source="history")
    for s in steps.get("m_bRepFormGList") or []:
        if not isinstance(s, dict) or s.get("ptr_class") != "BaseWallGStep":
            continue
        sv = _unwrap(s)
        for e in sv.get("m_faceHistTable") or []:
            key = tuple((e.get("m_faceHist") or {}).get("m_keys") or [])
            tags.faces[key] = int(e.get("m_id"))
        tags.edges = [int(e.get("m_id")) for e in (sv.get("m_edgeHistTable") or [])]
    for s in steps.get("m_nonBRepGList") or []:
        if not isinstance(s, dict) or s.get("ptr_class") != "WallRefPlanesGStep":
            continue
        sv = _unwrap(s)
        tags.refplanes = [int(e.get("m_id")) for e in (sv.get("m_faceHistTable") or [])]
    if not tags.complete:
        fresh = WallTags.fresh()
        for k, v in fresh.faces.items():
            tags.faces.setdefault(k, v)
        if len(tags.edges) < 12:
            tags.edges = fresh.edges
        if not tags.refplanes:
            tags.refplanes = fresh.refplanes
        tags.source = "history+fresh" if steps else "fresh"
    return tags


def wall_geometry_from_object(wall_obj: dict, base_z: Optional[float] = None,
                              height: Optional[float] = None) -> WallGeometry:
    """Recover the box from the wall's OWN seq-102 object: the location
    line (``m_pCurveDriver.m_pCrv`` = a ``GLine``: origin + t*dirVec over
    ``m_endParams``) and the ref-face planes (``m_pRefFaces``) whose signed
    offsets along ``n_left`` give the two side faces and whose envelope
    height gives the wall height.  ``base_z`` defaults to the line's z;
    ``height`` to the ref-face envelope height."""
    drv = _unwrap(wall_obj.get("m_pCurveDriver") or {})
    crv = _unwrap(drv.get("m_pCrv") or {})
    org = list(crv.get("m_origin") or [0.0, 0.0, 0.0])
    dvec = list(crv.get("m_dirVec") or [1.0, 0.0, 0.0])
    ep = list(crv.get("m_endParams") or [0.0, 1.0])
    n = math.hypot(dvec[0], dvec[1]) or 1.0
    u = [dvec[0] / n, dvec[1] / n, 0.0]
    p0 = [org[0] + u[0] * ep[0], org[1] + u[1] * ep[0], org[2]]
    p1 = [org[0] + u[0] * ep[1], org[1] + u[1] * ep[1], org[2]]
    n_left = [-u[1], u[0], 0.0]
    offs: List[float] = []
    env_h: Optional[float] = None
    for f in wall_obj.get("m_pRefFaces") or []:
        fv = _unwrap(f)
        surf = _unwrap(fv.get("m_pSurf") or {})
        fo = surf.get("m_origin")
        if not fo:
            continue
        offs.append((fo[0] - p0[0]) * n_left[0] + (fo[1] - p0[1]) * n_left[1])
        env = (surf.get("m_Envelope") or {}).get("m_corners")
        if env and len(env) > 1 and env_h is None:
            env_h = float(env[1][1] - env[0][1])
    if len(offs) < 2:
        raise ValueError("wall object carries no ref-face planes: cannot infer thickness")
    off_left, off_right = max(offs), min(offs)
    if abs(off_left - off_right) < 1e-9:
        raise ValueError("degenerate wall thickness from ref faces")
    bz = float(base_z) if base_z is not None else float(org[2])
    h = float(height) if height is not None else (env_h if env_h else 8.0)
    if h <= 0:
        raise ValueError(f"non-positive wall height {h}")
    return WallGeometry(p0=p0, p1=p1, base_z=bz, height=h,
                        off_left=float(off_left), off_right=float(off_right))


# ---------------------------------------------------------------------------
# archive numbering WITH weak-reference fix-up
# ---------------------------------------------------------------------------

def _renumber_with_weakrefs(value: dict, start: int = 3) -> int:
    """Number the owned-pointer tokens in Revit's ENCOUNTER order (the rule
    ``rvt.famgen.geometry.assign_pids`` implements) AND rewrite every weak
    reference through the old->new pid map.

    ``assign_pids`` alone leaves weakrefs untouched -- correct for a single
    subtree whose constructor computed its own weakrefs against the same
    numbering (``solid_box_brep``'s box at base 3), but WRONG the moment
    subtrees are COMPOSED (e.g. ref-plane groups prepended before the main
    solid shift its numbering).  Requirement: every subtree carries
    provisional pids that are GLOBALLY UNIQUE across the composed tree (our
    builders use disjoint bases), so old->new is unambiguous.  Weakref
    values 0 (null), 1 (document), 2 (root) are preserved.
    """
    counter = [int(start)]
    q: deque = deque()
    mapping: Dict[int, int] = {}

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if "ptr_class" in v:                       # owned/poly pointer
                if v["ptr_class"] in REGISTERED_CLASSES:
                    old = v.get("pid")
                    new = counter[0]
                    counter[0] += 1
                    if isinstance(old, int) and old > 2 and old not in mapping:
                        mapping[old] = new
                    v["pid"] = new
                else:
                    v["pid"] = -1
                q.append(v.get("value"))
            elif "weakref" in v or "backref_pid" in v or "classref" in v:
                return
            else:                                       # inline value class
                for x in v.values():
                    walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    while q:
        body = q.popleft()
        if body is not None:
            walk(body)

    def fix(v: Any) -> None:                            # pass 2: weakrefs
        if isinstance(v, dict):
            if "weakref" in v:
                w = v.get("weakref")
                if isinstance(w, int) and w > 2 and w in mapping:
                    v["weakref"] = mapping[w]
                return
            for x in v.values():
                fix(x)
        elif isinstance(v, list):
            for x in v:
                fix(x)

    if mapping:
        fix(value)
    return counter[0]


def weakref_report(value: dict) -> dict:
    """Consistency check of a numbered rep: every weak reference must point
    at the pid of a registered node in the same tree (or be 0/1/2 = null /
    document / root).  Returns {'pids', 'weakrefs', 'dangling'}; a correct
    rep has an EMPTY 'dangling'."""
    pids: set = set()
    weak: List[int] = []

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if "ptr_class" in v:
                p = v.get("pid")
                if isinstance(p, int) and p > 0:
                    pids.add(p)
                walk(v.get("value"))
                return
            if "weakref" in v:
                w = v.get("weakref")
                if isinstance(w, int):
                    weak.append(w)
                return
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    dangling = sorted({w for w in weak if w > 2 and w not in pids})
    return {"pids": len(pids), "weakrefs": len(weak), "dangling": dangling}


# ---------------------------------------------------------------------------
# the solid
# ---------------------------------------------------------------------------

def _retag(node: dict, tag_map: Dict[int, int]) -> None:
    """Rewrite ``m_GInfo.m_tag`` of every G-node in place via ``tag_map``."""
    if not isinstance(node, dict):
        return
    gi = node.get("m_GInfo")
    if isinstance(gi, dict) and gi.get("m_tag") in tag_map:
        gi["m_tag"] = int(tag_map[gi["m_tag"]])
    for k, v in node.items():
        if isinstance(v, dict):
            _retag(v.get("value") if "ptr_class" in v else v, tag_map)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    _retag(x.get("value") if "ptr_class" in x else x, tag_map)


def wall_solid_brep(geom: WallGeometry, tags: WallTags, *, element_id: int,
                    root_category_id: int = INVALID,
                    side_material_id: int = INVALID,
                    end_material_id: int = INVALID,
                    with_ref_planes: bool = False,
                    refplane_gstyle_id: int = INVALID,
                    ref_planes: Optional[Sequence[dict]] = None) -> dict:
    """Build the seq-103 ``GElement`` rep of a straight wall: ONE six-face
    box solid (12 edges), tagged with the wall's own history tags.

    ``root_category_id`` -- the ``GElement`` root's graphics category (a
    native wall's = its Walls-category projection ``GStyleElem``, e.g. 30;
    pass ``-1`` when the base carries no Walls GStyle -- the genesis
    lineage does NOT).  ``side_material_id`` -- ``Face.m_renderStyleId``
    of the two sides + top + bottom (the type's finish ``MaterialElem``);
    ``end_material_id`` -- the two end caps (native = the "Default Wall"
    core material); ``-1`` = category default appearance for either.
    ``with_ref_planes`` adds the four single-face ref-plane sub-graphics
    (``GGroup(cat=refplane_gstyle_id) -> Geometry(1 face)``) from
    ``ref_planes`` (the wall object's own ``m_pRefFaces``); native walls
    always carry them, but they are graphics-only (bisection knob).
    """
    if not tags.complete:
        raise ValueError("WallTags incomplete (need 6 face keys + 12 edge tags)")
    corners = geom.corners()
    # the proven six-face box: profile at the TOP, extruded DOWN to the base
    box = solid_box_brep(corners, geom.top_z, geom.base_z,
                         element_id=int(element_id), geometry_style_id=INVALID)
    # --- re-tag box tags -> the wall's history tags (values only) ----------
    # solid_box_brep: start cap (top) tag 1, end cap (bottom) tag 0,
    # sides 0..3 tags 2,5,9,13 = RIGHT, FAR cap, LEFT, START cap (see
    # WallGeometry.corners); its 12 edge tags 3,4,6,7,8,10,11,12,14,15,16,17.
    face_map = {
        1: tags.faces[KEY_TOP],
        0: tags.faces[KEY_BOTTOM],
        2: tags.faces[KEY_RIGHT],
        5: tags.faces[KEY_FAR],
        9: tags.faces[KEY_LEFT],
        13: tags.faces[KEY_START],
    }
    box_edge_tags = [3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17]
    edge_map = {bt: int(wt) for bt, wt in zip(box_edge_tags, tags.edges[:12])}
    tag_map = dict(face_map)
    tag_map.update(edge_map)
    # the Geometry node is the root's single sub-node
    geom_node = _unwrap(box["m_subNodes"][0])
    _retag(geom_node, tag_map)
    # --- wall-flavour face attributes: materials + flag calibration ---------
    material_by_tag = {
        tags.faces[KEY_LEFT]: side_material_id, tags.faces[KEY_RIGHT]: side_material_id,
        tags.faces[KEY_TOP]: side_material_id, tags.faces[KEY_BOTTOM]: side_material_id,
        tags.faces[KEY_START]: end_material_id, tags.faces[KEY_FAR]: end_material_id,
    }
    for f in geom_node.get("m_pFaces") or []:
        fv = _unwrap(f)
        ftag = (fv.get("m_GInfo") or {}).get("m_tag")
        fv["m_renderStyleId"] = int(material_by_tag.get(ftag, INVALID))
        fv["m_GInfo"]["m_flags"] = WALL_FACE_INFO_FLAGS
        fv["m_faceFlags_v9"] = WALL_FACE_FLAGS_V9
    # --- root: the element's category (Walls GStyle) or -1 ----------------
    box["m_GInfo"] = ginfo(category=int(root_category_id), tag=int(element_id),
                           flags=GELEM_ROOT_FLAGS)
    # --- optional ref-plane sub-graphics ----------------------------------
    if with_ref_planes and ref_planes:
        rp_nodes = _ref_plane_nodes(ref_planes, tags, refplane_gstyle_id)
        box["m_subNodes"] = rp_nodes + list(box["m_subNodes"])
    # renumber the archive pids over the FINAL tree AND rewrite the weak
    # references through the old->new map (the box computed its weakrefs
    # against base 3; the ref planes against disjoint bases 200/210/...:
    # composing them shifts the numbering, so a bare assign_pids -- which
    # leaves weakrefs alone -- would strand every Edge->Face / loop link).
    # With no ref planes the box's numbering is reproduced unchanged.
    _renumber_with_weakrefs(box)
    rep = weakref_report(box)
    if rep["dangling"]:
        raise AssertionError(f"wall rep has dangling weakrefs {rep['dangling'][:8]} "
                             "(pid numbering / weakref fix-up mismatch)")
    return box


# ---------------------------------------------------------------------------
# ref-plane sub-graphics (single planar face each) -- native walls carry 4
# ---------------------------------------------------------------------------

def _single_face_geometry(origin: Vec, xvec: Vec, yvec: Vec, u_len: float,
                          v_len: float, *, tag: int = -1,
                          material_id: int = INVALID, base_pid: int = 3) -> dict:
    """A one-face ``Geometry`` (a rectangle on ``origin + a*xvec + b*yvec``,
    a in [0,u_len], b in [0,v_len]) with its 4 edges and closed loop -- the
    shape of a native wall's ref-plane sub-graphic.  Pids are placeholders
    (the caller renumbers the whole tree with ``assign_pids``)."""
    o = [float(t) for t in origin]
    x = [float(t) for t in xvec]
    y = [float(t) for t in yvec]
    env = [[0.0, 0.0], [float(u_len), float(v_len)]]

    def p(a, b):
        return [o[i] + x[i] * a + y[i] * b for i in range(3)]

    # 4 corners in the face's own uv, CCW
    uv = [[0.0, 0.0], [u_len, 0.0], [u_len, v_len], [0.0, v_len]]
    # pid layout: geometry base_pid, face +1, edges +2..+5, loop +6, plane +7
    p_geo = base_pid
    p_face = base_pid + 1
    p_edges = [base_pid + 2 + i for i in range(4)]
    p_loop = base_pid + 6
    p_plane = base_pid + 7

    lp = blank_object("EdgeLoop")
    lp["m_GInfo"] = ginfo(flags=LOOP_INFO_FLAGS)
    lp["m_nextLoop"] = None
    lp["m_pFace"] = _weak(p_face)
    lp["m_next"] = _weak(p_edges[0])
    lp["m_prev"] = _weak(p_edges[-1])
    lp["m_Envelope"] = {"m_corners": [list(env[0]), list(env[1])]}
    lp["m_open"] = False

    face = blank_object("Face")
    face["m_GInfo"] = ginfo(tag=tag, flags=WALL_FACE_INFO_FLAGS)
    face["m_pFirstLoop"] = _ptr("EdgeLoop", lp, p_loop)
    face["m_faceRegions"] = []
    face["m_pGFilling"] = None
    face["m_oBackgroundFilling"] = None
    face["m_renderStyleId"] = int(material_id)
    face["m_cutType"] = 0
    face["m_faceFlags_v9"] = WALL_FACE_FLAGS_V9
    surf = plane(o, x, y, env)
    surf["pid"] = p_plane
    face["m_pSurf"] = surf

    edges = []
    for i in range(4):
        a0, b0 = uv[i]
        a1, b1 = uv[(i + 1) % 4]
        e = blank_object("Edge")
        e["m_GInfo"] = ginfo(tag=-1, flags=EDGE_INFO_FLAGS)
        # single face: both face slots reference the same face / null second
        e["m_pFace"] = [_weak(p_face), _weak(0)]
        e["m_next"] = [_weak(p_edges[(i + 1) % 4] if i + 1 < 4 else p_loop), _weak(0)]
        e["m_prev"] = [_weak(p_edges[i - 1] if i > 0 else p_loop), _weak(0)]
        e["m_interiorEdgePnts"] = []
        e["m_firstAndLastEdgePnts"] = [
            {"uv": [[a0, b0], [0.0, 0.0]]},
            {"uv": [[a1, b1], [0.0, 0.0]]},
        ]
        e["m_flags"] = EDGE_FLAGS_FORWARD_IN_A
        edges.append(_ptr("Edge", e, p_edges[i]))
    # close the chain: last edge's next / first edge's prev -> the loop
    _unwrap(edges[-1])["m_next"] = [_weak(p_loop), _weak(0)]
    _unwrap(edges[0])["m_prev"] = [_weak(p_loop), _weak(0)]

    geo = blank_object("Geometry")
    geo["m_GInfo"] = ginfo(category=INVALID, tag=-1, flags=GEOMETRY_FLAGS)
    geo["m_pFaces"] = [_ptr("Face", face, p_face)]
    geo["m_flags"] = 7
    geo["m_geometryTag"] = INVALID
    geo["m_tessEpsCntrl"] = {"m_type": 0, "m_TessEpsCntrlVersion": 1}
    geo["m_pEdges"] = edges
    geo["m_sharedSurfInfo"] = []
    return _ptr("Geometry", geo, p_geo)


def _ref_plane_nodes(ref_planes: Sequence[dict], tags: WallTags,
                     gstyle_id: int) -> List[dict]:
    """One ``GGroup(cat=gstyle_id) -> single-face Geometry`` per ref-plane
    face of the wall object's ``m_pRefFaces`` (each = {'origin','xvec',
    'yvec','u_len','v_len'} in feet, and optionally 'tag')."""
    out = []
    for i, rp in enumerate(ref_planes):
        gtag = rp.get("tag")
        if gtag is None:
            gtag = tags.refplanes[i] if i < len(tags.refplanes) else -1
        # a DISTINCT provisional pid base per subtree (200, 210, ...) so
        # the composed tree's old->new weakref map is unambiguous
        face_geo = _single_face_geometry(rp["origin"], rp["xvec"], rp["yvec"],
                                         rp["u_len"], rp["v_len"], tag=-1,
                                         material_id=INVALID,
                                         base_pid=200 + 10 * i)
        grp = blank_object("GGroup")
        grp["m_GInfo"] = ginfo(category=int(gstyle_id), tag=int(gtag),
                                flags=REFPLANE_GROUP_FLAGS)
        grp["m_subNodes"] = [face_geo]
        out.append(_ptr("GGroup", grp))
    return out


def ref_planes_from_wall_object(wall_obj: dict) -> List[dict]:
    """Convert the wall object's ``m_pRefFaces`` planes into the
    ``ref_planes`` list :func:`wall_solid_brep` accepts (origin / axes /
    envelope of each driven reference face, feet)."""
    out = []
    for f in wall_obj.get("m_pRefFaces") or []:
        fv = _unwrap(f)
        surf = _unwrap(fv.get("m_pSurf") or {})
        o = surf.get("m_origin")
        x = surf.get("m_xVec")
        y = surf.get("m_yVec")
        env = (surf.get("m_Envelope") or {}).get("m_corners") or [[0, 0], [1, 1]]
        if not (o and x and y):
            continue
        out.append({"origin": list(o), "xvec": list(x), "yvec": list(y),
                    "u_len": float(env[1][0] - env[0][0]),
                    "v_len": float(env[1][1] - env[0][1]),
                    "tag": (fv.get("m_GInfo") or {}).get("m_tag")})
    return out


# ---------------------------------------------------------------------------
# convenience: rep straight from a (cloned) wall's seq-102 object
# ---------------------------------------------------------------------------

def wall_rep_from_object(wall_obj: dict, *, element_id: int,
                         base_z: Optional[float] = None,
                         height: Optional[float] = None,
                         root_category_id: int = INVALID,
                         side_material_id: int = INVALID,
                         end_material_id: int = INVALID,
                         with_ref_planes: bool = False,
                         refplane_gstyle_id: int = INVALID) -> Tuple[dict, WallGeometry, WallTags]:
    """The whole recipe: read geometry + tags off the wall's own object and
    build its rep.  Returns ``(gelement, geometry, tags)``."""
    geom = wall_geometry_from_object(wall_obj, base_z=base_z, height=height)
    tags = tags_from_wall_object(wall_obj)
    ref_planes = ref_planes_from_wall_object(wall_obj) if with_ref_planes else None
    rep = wall_solid_brep(geom, tags, element_id=element_id,
                          root_category_id=root_category_id,
                          side_material_id=side_material_id,
                          end_material_id=end_material_id,
                          with_ref_planes=with_ref_planes,
                          refplane_gstyle_id=refplane_gstyle_id,
                          ref_planes=ref_planes)
    return rep, geom, tags


__all__ = [
    "CLASS_GELEMENT", "WallGeometry", "WallTags",
    "tags_from_wall_object", "wall_geometry_from_object",
    "ref_planes_from_wall_object", "wall_solid_brep", "wall_rep_from_object",
]

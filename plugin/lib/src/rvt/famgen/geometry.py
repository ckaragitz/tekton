"""rvt.famgen.geometry -- parametric FORM generators for Revit family documents.

Turn plain dimensions into OUR OWN family geometry: the profile sketch, the
sketch's ``CurveElem`` lines, the ``ExtrusionElem`` form and its cached
six-face B-rep solid, all constructed FIELD BY FIELD from parameters.  The
expression is ours; only the numbers (manufacturer dimensions) are facts
(``docs/product/content-strategy.md``).  Nothing here is cloned from an
Autodesk payload -- the specimen families were MEASURED to derive the
structural rules, which are reproduced here as code (the same discipline
as ``rvt.genesis.types`` / ``rvt.genesis.skeleton``).

What a family FORM is on disk (tekton stream ``family-geometry``,
2026-08-03; evidence in ``docs/writer/family-geometry.md``)::

    ExtrusionElem  (seq 102)
      m_pParamValueSetDouble  {-1001801: end offset, -1001800: start offset}
                               (feet, along the sketch normal; end < start
                                in every box specimen = "extrude down")
      m_geomSteps             GeomStepList{ ExtrusionGStep{ faceHistTable,
                               edgeHistTable } }   <- the topology TAG map
      m_pGeomTable            GeomTable{ tag index -> generator id }
      m_cellList              ExtrusionElemExtrusionHelper{ m_sketchId,
                               m_pCurveLoops[ CurveLoop{ GLine* } ] }
                               (a private COPY of the profile loop)
    ExtrusionElem  (seq 103)   GElement{ Geometry{ 6 Face + 12 Edge,
                               EdgeLoop/Plane per face, uv co-edges } }
                               = the cached solid; or SerializedDummy
    VarSketch      (seq 102)   the sketch (m_absorbedCurves = the drawn
                               lines, m_elemIdsPairSet -> its CurveElems,
                               m_sketchPlaneId, m_userId = the extrusion)
    VarSketch      (seq 103)   GElement{ GLine* } (gElemType 2)
    CurveElem x n  (seq 102)   one per profile line (m_pCurveDriver.m_pCrv =
                               GLine, joins to its neighbours, SketchMembership)
    CurveElem      (seq 103)   GElement{ GLine } (gElemType 2)
    SketchPlane    (seq 102)   the sketch's plane ON the 'Ref. Level' datum
                               (m_oPlaneRef.m_datumPlaneId = level id)
    SketchPlane    (seq 103)   SerializedDummy

The B-rep topology of a rectangular-profile extrusion is a FIXED TEMPLATE
(verified pid-for-pid / weakref-for-weakref on two independent specimen
boxes, ``docs/writer/family-geometry.md`` sec. 3): only the frames, uv
coordinates and envelopes vary.  :func:`solid_box_brep` reproduces that
template from six numbers (the profile rectangle and the two offsets) --
the topology reproduction test in ``tests/test_famgen_geometry.py`` rebuilds
BOTH specimen solids from their dimensions and compares them to the decoded
originals leaf by leaf.

Shape contract: every constructor returns :class:`rvt.genesis.skeleton.
SkelElement` records (seq-101 header + seq-102 object + seq-103 rep), so
the commit / assembly layers treat family FORM elements exactly like
skeleton and type records.  :class:`FormBundle` groups the cluster of a
form (sketch plane, sketch, curve elems, extrusion) and can splice itself
into a donor ``.rfa`` (:func:`emit_form_rfa`) for the acceptance proof.

Run ``python -m rvt.famgen.geometry`` to build the proof families
(``experiments/families/genesis/G_box_solid.rfa`` / ``G_box_dummy.rfa``)
and the topology-reproduction report.
"""
from __future__ import annotations

import copy
import json
import math
import os
import struct
from collections import deque
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..genesis.skeleton import SkelElement, IdSource, element_header
from ..genesis.types import (blank_object, element_defaults, mm, inches,
                             INVALID, class_id as _class_id)

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))  # repo root; env TEKTON_ROOT overrides
SAMPLE_RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                          "racbasicsamplefamily-2026.rfa")
OUT_DIR = os.path.join(ROOT, "experiments", "families", "genesis")

Vec = Sequence[float]

# ---------------------------------------------------------------------------
# BuiltInParameter / class constants (Revit 2026, verified on the corpus)
# ---------------------------------------------------------------------------

BIP_EXTRUSION_START = -1001800    #: ExtrusionElem start offset (ft) [V]
BIP_EXTRUSION_END = -1001801      #: ExtrusionElem end offset (ft)   [V]
BIP_CURVE_ELEM_INT = -1006205     #: int 1 on every model CurveElem/Extrusion [V, name INFERRED]

FAMILY_DESIGN_OPTION = -4         #: m_designOptionId of every element in a family doc [V]
NO_DESIGN_OPTION = -1

#: SerializedDummy rep => rely on Revit REGENERATION to build the solid (F4b)
REP_DUMMY = "dummy"
#: GElement rep => we author the cached B-rep solid ourselves (F4a)
REP_SOLID = "solid"

# ---------------------------------------------------------------------------
# GObject / element flag constants (per specimen; docs/writer/family-geometry.md)
# ---------------------------------------------------------------------------

#: GLine m_GInfo.m_flags for curve GEOMETRY carried inside objects (the
#: extrusion helper loop, the sketch's absorbed curves, the CurveElem
#: driver).  Standalone .rfa flavour = 0x1000004; the same lines inside a
#: PROJECT-embedded family document carry bit 19 (0x1080004).  [V]
GLINE_FLAGS_RFA = 0x1000004        # 16777220
GLINE_FLAGS_EMBEDDED = 0x1080004   # 17301508
#: the seq-103 REP copies add 0x8000 (sketch rep) / 0x8200 (curve elem rep) [V]
GLINE_REP_SKETCH_DELTA = 0x8000
GLINE_REP_CURVE_DELTA = 0x8200

#: GElement / Geometry / Face / Edge / EdgeLoop m_GInfo.m_flags (identical
#: in the .rfa and the embedded specimens) [V]
GELEM_ROOT_FLAGS = 557060
GELEM_CURVE_ROOT_FLAGS = 561156
GEOMETRY_FLAGS = 573444
FACE_FLAGS = 558596               # (786837 carries bit 0x200 clear on 5 faces)
EDGE_INFO_FLAGS = 557572          # 3/4 solids; 786837 carries 557060 (0x200 clear)
LOOP_INFO_FLAGS = 524292
#: GInfo.m_flags bit that differs between two boxes of the SAME Autodesk
#: family (786837 clears it on faces+edges, 786867 sets it): a volatile
#: graphics-cache bit, not derivable from dimensions and irrelevant to
#: acceptance (both open).  The topology proof compares modulo it. [V]
GINFO_VOLATILE_BIT = 0x200
#: Edge.m_flags: 6 = the stored parametric direction is FORWARD in
#: m_pFace[0]'s loop; bit 0 set (7) = it is REVERSED there [V, sec. 3.4]
EDGE_FLAGS_FORWARD_IN_A = 6
EDGE_FLAGS_REVERSED_IN_A = 7

#: per-class ElementHeader (m_abFlags4Bytes, m_nVisibleViewFlags) in a
#: standalone .rfa (the project-embedded copies differ by bit 0x10 on the
#: first three) [V both specimens]
HDR_FLAGS = {
    "SketchPlane": (26, -32768),
    "VarSketch": (16779322, -32768),
    "ExtrusionElem": (3896, -4225),
    "CurveElem": (17340539, -4225),
}
HDR_FLAGS_EMBEDDED = {
    "SketchPlane": (10, -32768),
    "VarSketch": (16779306, -32768),
    "ExtrusionElem": (3880, -4225),
    "CurveElem": (17338475, -4225),
}

BIC_LINES = -2000045   #: OST_Lines: model-line CurveElem category [V]


# ---------------------------------------------------------------------------
# family-document context (what the donor / skeleton document supplies)
# ---------------------------------------------------------------------------

@dataclass
class FamilyDocContext:
    """The document-side facts a form needs to reference.

    ``family_id`` -- the doc's self-``Family`` (every element's ``m_famId``
    and the header ``m_familyId``); ``level_id`` -- the 'Ref. Level' the
    sketch plane sits on (its datum); ``geometry_style_id`` -- the
    ``GStyleElem`` id the solid's ``Geometry`` node references as its
    graphics category (the family's own <category> object style);
    ``curve_style_id`` -- the ``GStyleElem`` id the CurveElem's rep line
    references; ``extra_regen_ids`` -- ids the donor's own extrusion lists
    in ``m_regenOnly`` besides its sketch plane (its origin ref plane).
    All discoverable from a donor via :func:`context_from_rfa`.
    """
    family_id: int = 17
    level_id: int = 21
    geometry_style_id: int = -1
    curve_style_id: int = -1
    solid_control_command: int = 0
    extra_regen_ids: List[int] = dc_field(default_factory=list)
    embedded: bool = False            # project-embedded flavour (flag bits)
    #: ``ExtrusionElem.m_famElemVisibility`` -- the Family Element Visibility
    #: Settings bitfield.  Bit 0 is "Plan/RCP"; the value measured off the
    #: donor (57398) has it CLEAR, i.e. that family's author had switched
    #: Plan/RCP display OFF, and we inherited the choice on every form we
    #: ship -- so a generated family drew nothing in its own plan and ceiling
    #: views no matter what the views said [owner screenshot: "Display in 3D
    #: views and:" with Plan/RCP unticked].  Revit's own default for a new
    #: form has all three view boxes ticked; 57399 = 57398 | Plan/RCP.
    FAM_ELEM_VISIBILITY_ALL_VIEWS = 57399
    fam_elem_visibility: int = 57399  # ExtrusionElem.m_famElemVisibility
    #: Geometry.m_tessEpsCntrl.m_TessEpsCntrlVersion of the donor's own
    #: forms: 0 in the standalone sample .rfa, 1 in the rme-embedded
    #: panelboard family (both load) [V]; matched to the donor.
    tess_version: int = 1

    @property
    def hdr(self) -> dict:
        return HDR_FLAGS_EMBEDDED if self.embedded else HDR_FLAGS

    @property
    def gline_flags(self) -> int:
        return GLINE_FLAGS_EMBEDDED if self.embedded else GLINE_FLAGS_RFA


def context_from_rfa(path: str = SAMPLE_RFA) -> FamilyDocContext:
    """Discover the :class:`FamilyDocContext` of a family document by
    reading its own extrusion / curve-elem specimens (no hard-coding)."""
    from ..families import FamilyIndex, self_family_of_unit
    idx = FamilyIndex(path)
    unit = 0
    ctx = FamilyDocContext()
    sf = self_family_of_unit(idx, unit)
    if sf:
        ctx.family_id = int(sf["id"])
    lv = idx.ids_of_class(unit, "Level")
    if lv:
        ctx.level_id = int(lv[0])
    rfclass = idx.schema.by_name.get("RefPlane")
    refplanes = set(idx.ids_of_class(unit, "RefPlane")) if rfclass else set()
    for eid in idx.ids_of_class(unit, "ExtrusionElem"):
        rep = idx.decode(unit, eid, 103)
        if rep is not None and rep.clean and idx.class_name(
                idx.unit_records(unit)[103][eid].class_id) == "GElement":
            geo = (rep.value.get("m_subNodes") or [{}])[0].get("value") or {}
            gi = geo.get("m_GInfo") or {}
            ctx.geometry_style_id = int(gi.get("m_categoryId", -1))
            ctx.solid_control_command = int(gi.get("m_controlCommand", 0))
            te = geo.get("m_tessEpsCntrl") or {}
            ctx.tess_version = int(te.get("m_TessEpsCntrlVersion", ctx.tess_version))
        v = idx.value(unit, eid) or {}
        # adopt the specimen's bitfield but never its "hidden in Plan/RCP"
        # choice -- that is the author's UI preference, not a format law
        ctx.fam_elem_visibility = int(
            (v.get("m_famElemVisibility") or {}).get(
                "m_flags", GeometryContext.FAM_ELEM_VISIBILITY_ALL_VIEWS)) | 1
        h = idx.value(unit, eid, 101) or {}
        regen = ((h.get("m_parents") or {}).get("value") or {}).get("m_regenOnly") or []
        ctx.extra_regen_ids = [int(r) for r in regen if r in refplanes]
        break
    for eid in idx.ids_of_class(unit, "CurveElem"):
        rep = idx.decode(unit, eid, 103)
        if rep is not None and rep.clean:
            gi = rep.value.get("m_GInfo") or {}
            if int(gi.get("m_categoryId", -1)) >= 0:
                ctx.curve_style_id = int(gi["m_categoryId"])
                break
    return ctx


# ---------------------------------------------------------------------------
# archive object-index (pid) assignment -- the encoder's numbering, mimicked
# ---------------------------------------------------------------------------

#: The classes whose owned instances the archive REGISTERS (given a real
#: object index / "pid"); every other class serializes pid -1.  Discovered
#: exhaustively over 6,296 records (the sample .rfa + two embedded family
#: documents): the two sets are DISJOINT and this list reproduces the
#: original pid of EVERY pointer in EVERY record (tests). [V]
REGISTERED_CLASSES = frozenset({
    "Edge", "EdgeLoop", "Face", "FamilyDocument", "GArc", "GBitmap",
    "GElement", "GFilling", "GFilter", "GGTag", "GGroup", "GLine",
    "GPoint", "GPolyMesh", "Geometry", "Plane", "VarParam",
    "VarSketchArcEndAngleConstrObj", "VarSketchArcObj",
    "VarSketchHorVerConstrObj", "VarSketchLSegPerpToLSegConstrObj",
    "VarSketchLineSegObj", "VarSketchPPConstrObj",
})


def assign_pids(value: dict, start: int = 3) -> int:
    """Number the owned-pointer tokens of an object dict IN PLACE, exactly
    as Revit's archive numbers them (and as ``rvt.encode`` writes them).

    Rule (verified 6,296/6,296 records): pid 1 = the document, pid 2 = the
    record's root object; further indices are handed out in ENCOUNTER
    order -- the root's fields in schema order (inline value structs
    recurse in place), owned pointers queue their bodies breadth-first --
    but only instances of :data:`REGISTERED_CLASSES` receive an index
    (everything else keeps -1).  Weak references are left untouched (the
    constructors compute them from the same numbering).  Returns the next
    free index.
    """
    counter = [int(start)]
    q: deque = deque()

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if "ptr_class" in v:                       # owned/poly pointer
                v["pid"] = (counter[0] if v["ptr_class"] in REGISTERED_CLASSES
                            else -1)
                if v["ptr_class"] in REGISTERED_CLASSES:
                    counter[0] += 1
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
    return counter[0]


# ---------------------------------------------------------------------------
# small vector algebra (feet; pure python, no numpy)
# ---------------------------------------------------------------------------

def _v(p) -> List[float]:
    return [float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, k: float):
    return [a[0] * k, a[1] * k, a[2] * k]


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    if n == 0:
        raise ValueError("zero-length vector")
    return [a[0] / n, a[1] / n, a[2] / n]


def _neg(a):
    return [-a[0], -a[1], -a[2]]


def _clean(x: float, eps: float = 1e-12) -> float:
    """Squash float noise to exact zero (our expression is clean by design)."""
    return 0.0 if abs(x) < eps else float(x)


def _cv(a) -> List[float]:
    return [_clean(a[0]), _clean(a[1]), _clean(a[2])]


def _uv(a) -> List[float]:
    return [_clean(a[0]), _clean(a[1])]


def polygon_area_xy(vertices: Sequence[Vec]) -> float:
    """Signed shoelace area of a polygon in the xy plane (>0 = CCW)."""
    a = 0.0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i][0], vertices[i][1]
        x2, y2 = vertices[(i + 1) % n][0], vertices[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return a / 2.0


# ---------------------------------------------------------------------------
# G-object builders (schema-blank + overlay => encoder-ready dicts)
# ---------------------------------------------------------------------------

def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": int(pid), "value": value}


def _owned(cls: str, **overlay) -> dict:
    v = blank_object(cls)
    for k, val in overlay.items():
        if k not in v:
            raise KeyError(f"{cls} has no field {k!r}")
        v[k] = val
    return _ptr(cls, v)


def _weak(pid: int) -> dict:
    return {"weakref": int(pid)}


def ginfo(*, category: int = -1, tag: int = -1, control_command: int = 0,
          flags: int = 0) -> dict:
    """A ``GInfo`` value struct (every G-object's header)."""
    g = blank_object("GInfo")
    g["m_categoryId"] = int(category)
    g["m_tag"] = int(tag)
    g["m_controlCommand"] = int(control_command)
    g["m_flags"] = int(flags)
    return g


def gline(origin: Vec, direction: Vec, t0: float, t1: float, *, tag: int = -1,
          flags: int = GLINE_FLAGS_RFA, category: int = -1) -> dict:
    """An owned ``GLine`` token: points = origin + t*dirVec, t in [t0, t1].

    ``direction`` is normalised (Revit stores unit dirVec with the
    parametric interval carrying the length).
    """
    v = blank_object("GLine")
    v["m_GInfo"] = ginfo(category=category, tag=tag, flags=flags)
    v["m_endParams"] = [_clean(t0), _clean(t1)]
    v["m_origin"] = _cv(_v(origin))
    v["m_dirVec"] = _cv(_unit(_v(direction)))
    return _ptr("GLine", v)


def gline_between(p0: Vec, p1: Vec, *, tag: int = -1, flags: int = GLINE_FLAGS_RFA,
                  category: int = -1, anchor: str = "start") -> dict:
    """A ``GLine`` from p0 to p1.

    ``anchor='start'`` -> origin p0, interval [0, len] (the "as drawn"
    parametrization the sketch's absorbed curves / CurveElem drivers use);
    ``anchor='end'`` -> origin p1, interval [-len, 0] (the parametrization
    Revit's traced extrusion loop uses for the curves it reverses). [V]
    """
    p0, p1 = _v(p0), _v(p1)
    d = _sub(p1, p0)
    length = _norm(d)
    if anchor == "end":
        return gline(p1, d, -length, 0.0, tag=tag, flags=flags, category=category)
    return gline(p0, d, 0.0, length, tag=tag, flags=flags, category=category)


def garc(center: Vec, radius: float, ang0: float, ang1: float, *, tag: int = -1,
         xvec: Vec = (1.0, 0.0, 0.0), yvec: Vec = (0.0, 1.0, 0.0),
         flags: int = GLINE_FLAGS_RFA, category: int = -1) -> dict:
    """An owned ``GArc`` token: center + radius(cos t xVec + sin t yVec),
    t in [ang0, ang1] (radians; CCW positive)."""
    v = blank_object("GArc")
    v["m_GInfo"] = ginfo(category=category, tag=tag, flags=flags)
    v["m_endParams"] = [float(ang0), float(ang1)]
    v["m_xVec"] = _cv(_v(xvec))
    v["m_yVec"] = _cv(_v(yvec))
    v["m_radius"] = float(radius)
    v["m_center"] = _cv(_v(center))
    v["m_bFilled"] = False
    return _ptr("GArc", v)


def plane(origin: Vec, xvec: Vec, yvec: Vec, corners: Sequence[Vec], *,
          orient: bool = True) -> dict:
    """An owned ``Plane`` (surface / sketch plane) token with its uv
    envelope ``corners = [[umin, vmin], [umax, vmax]]``."""
    v = blank_object("Plane")
    v["m_Envelope"] = {"m_corners": [_uv(corners[0]), _uv(corners[1])]}
    v["m_orientFlag"] = bool(orient)
    v["m_origin"] = _cv(_v(origin))
    v["m_xVec"] = _cv(_v(xvec))
    v["m_yVec"] = _cv(_v(yvec))
    return _ptr("Plane", v)


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------

@dataclass
class RectProfile:
    """A rectangle in the sketch plane: 4 vertices, COUNTER-CLOCKWISE
    (the orientation Revit's extrusion loop tracer stores) [V]."""
    vertices: List[List[float]]        # 4 x [x, y, 0]

    @property
    def width(self) -> float:
        xs = [v[0] for v in self.vertices]
        return abs(max(xs) - min(xs))          # bounding box: exact for a
                                               # rectangle, meaningful for the
                                               # arbitrary rings polygon_profile
                                               # accepts (issue #498)

    @property
    def depth(self) -> float:
        ys = [v[1] for v in self.vertices]
        return abs(max(ys) - min(ys))

    def center(self) -> List[float]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return [(min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, 0.0]


def rect_profile(width_ft: float, depth_ft: float, *,
                 center: Vec = (0.0, 0.0)) -> RectProfile:
    """A width x depth rectangle centred at ``center`` (feet), CCW from the
    +x/+y corner: V0=(+,+), V1=(-,+), V2=(-,-), V3=(+,-).

    This vertex order is the one both box specimens' traced loops use
    (curve 0 = the top edge running -x) so the derived B-rep matches the
    specimen pid/weakref template exactly. [V]
    """
    if width_ft <= 0 or depth_ft <= 0:
        raise ValueError("width/depth must be positive")
    cx, cy = float(center[0]), float(center[1])
    hw, hd = width_ft / 2.0, depth_ft / 2.0
    return RectProfile([
        [cx + hw, cy + hd, 0.0],   # V0
        [cx - hw, cy + hd, 0.0],   # V1
        [cx - hw, cy - hd, 0.0],   # V2
        [cx + hw, cy - hd, 0.0],   # V3
    ])


def profile_from_vertices(vertices: Sequence[Vec]) -> RectProfile:
    """Wrap 4 explicit CCW vertices (used by the specimen-reproduction test)."""
    vs = [_v(p) for p in vertices]
    if len(vs) != 4:
        raise ValueError("box profile needs exactly 4 vertices")
    if polygon_area_xy(vs) <= 0:
        raise ValueError("profile vertices must be counter-clockwise")
    return RectProfile([[v[0], v[1], 0.0] for v in vs])


def polygon_profile(vertices: Sequence[Vec]) -> RectProfile:
    """An ARBITRARY closed planar profile (issue #498: any 3D object, not
    just catalog boxes) -- N >= 3 vertices in the sketch plane, returned in
    the counter-clockwise order Revit's extrusion loop tracer stores.

    Clockwise input is reversed rather than refused (an IFC profile's
    winding follows its own axis convention); the last vertex must not
    repeat the first (a closed ring is implied, as ``prism_form`` wraps
    modulo n).  ``RectProfile``'s width / depth / center read the bounding
    box, so they stay meaningful for a non-rectangular ring.
    """
    vs = [_v(p) for p in vertices]
    if len(vs) >= 2 and abs(vs[0][0] - vs[-1][0]) < 1e-12 \
            and abs(vs[0][1] - vs[-1][1]) < 1e-12:
        vs = vs[:-1]                              # drop a repeated closing point
    if len(vs) < 3:
        raise ValueError(f"a profile needs at least 3 distinct vertices (got {len(vs)})")
    if polygon_area_xy(vs) < 0:
        vs = list(reversed(vs))                   # normalise to counter-clockwise
    if polygon_area_xy(vs) <= 0:
        raise ValueError("profile vertices are collinear or zero-area")
    return RectProfile([[v[0], v[1], 0.0] for v in vs])


# ---------------------------------------------------------------------------
# the six-face solid: topology template (docs/writer/family-geometry.md sec. 3)
# ---------------------------------------------------------------------------

def _box_tags(n: int) -> dict:
    """Geometry-history TAG allocation for an n-curve profile extrusion,
    as Revit's ExtrusionGStep records it [V, both box specimens; formula
    reproduces the 4-circle leg extrusion's per-loop pattern too]:

      tag 0 = end cap face, tag 1 = start cap face; then walking the loop:
      for curve i: side face, start rail [1,i,0], end rail [1,i,1], and
      (from i=1) the lateral [2,i-1,i]; finally the closing lateral
      [2,n-1,0].  Total = 2 + 4n tags (18 for a box).
    """
    face_tag: List[int] = []
    rail_s: List[int] = []
    rail_e: List[int] = []
    lateral: List[Optional[int]] = [None] * n     # lateral[i] = vertex V(i+1) (i<n-1); lateral[n-1] = closing at V0
    t = 2
    for i in range(n):
        face_tag.append(t); t += 1
        rail_s.append(t); rail_e.append(t + 1); t += 2
        if i > 0:
            lateral[i - 1] = t; t += 1
    lateral[n - 1] = t; t += 1
    return {"end_face": 0, "start_face": 1, "face": face_tag,
            "rail_start": rail_s, "rail_end": rail_e, "lateral": lateral,
            "count": t}


def solid_box_brep(profile: RectProfile | Sequence[Vec], start: float, end: float,
                   *, element_id: int, geometry_style_id: int = -1,
                   control_command: int = 0,
                   base_pid: int = 3) -> dict:
    """The cached (N+2)-face B-rep solid (seq-103 ``GElement``) of a PRISM
    over any closed planar profile, built field by field.

    Generalised from the 4-gon on measured evidence that the alternative
    does not exist: a form shipped with the SerializedDummy "regeneration"
    rep draws NOTHING in Revit [owner probe, concave L-bracket + cylinder +
    cap: the two cached-B-rep parts rendered, the regeneration part was
    absent].  Revit does not rebuild a family form's solid from its sketch
    on open, so every form needs a real cached solid -- and an N-gon prism
    is the SAME topology as the box (2 caps + N sides, 3N edges, tags from
    :func:`_box_tags`, whose numbering was already written for N).  Nothing
    below was specific to 4; only the guard was.

    ``profile`` -- >= 3 CCW vertices in the sketch plane (z ignored);
    ``start`` / ``end`` -- offsets along the sketch normal (+z), with
    ``start > end`` (the "extrude-down" convention of every box specimen:
    the START cap is the top face).  ``element_id`` becomes the root tag /
    ``m_elementId``; ``geometry_style_id`` = the ``Geometry`` graphics
    category (the family sub-category ``GStyleElem`` id).

    Structure (identical archive numbering in both specimens) [V]::

        GElement (pid 2) -> Geometry (3)
          m_pFaces = [start cap (4, tag 1), end cap (5, tag 0),
                      side_0..side_3 (6..9, tags 2,5,9,13)]
          m_pEdges = 12 Edge (10..21, tags 3,4,6,7,8,10,11,12,14,15,16,17)
          each Face -> EdgeLoop (22,24,..) + Plane surface (23,25,..)
        edges reference their two faces by weakref, carry next/prev
        weakrefs per face loop and their two endpoints' uv coordinates in
        BOTH adjacent face frames (m_firstAndLastEdgePnts = [first point
        {uv in face A, uv in face B}, last point {...}]).

    See ``docs/writer/family-geometry.md`` sec. 3 for the frame / loop /
    direction rules with specimen evidence.  Returns the GElement dict (the
    caller wraps it as the seq-103 rep of the ExtrusionElem).
    """
    prof = profile if isinstance(profile, RectProfile) else polygon_profile(profile)
    V = [_v(p) for p in prof.vertices]
    n = len(V)
    if n < 3:
        raise ValueError(f"a prism profile needs at least 3 vertices (got {n})")
    if polygon_area_xy(V) <= 0:
        raise ValueError("profile must be counter-clockwise (viewed from +z)")
    zs, ze = float(start), float(end)
    if not zs > ze:
        raise ValueError("box specimens are extrude-DOWN: require start > end "
                         "(the start cap is the top face)")
    tags = _box_tags(n)
    depth = zs - ze                       # extrusion length (> 0)
    ext = [0.0, 0.0, -1.0]                # unit direction start -> end
    up = [0.0, 0.0, 1.0]                  # start cap outward normal
    dn = [0.0, 0.0, -1.0]                 # end cap outward normal

    def at(p, z):                          # profile vertex lifted to plane z
        return [p[0], p[1], z]

    top = [at(p, zs) for p in V]
    bot = [at(p, ze) for p in V]
    tan = [_unit(_sub(V[(i + 1) % n], V[i])) for i in range(n)]     # curve tangents
    length = [_norm(_sub(V[(i + 1) % n], V[i])) for i in range(n)]

    # --- archive numbering: Geometry, faces, edges, then (loop, plane) pairs
    p_geometry = base_pid                       # 3
    n_faces = 2 + n                             # 6
    n_edges = 3 * n                             # 12
    fpid = [p_geometry + 1 + k for k in range(n_faces)]          # 4..9
    epid_base = fpid[-1] + 1                                     # 10
    lp_base = epid_base + n_edges                                # 22
    loop_pid = [lp_base + 2 * k for k in range(n_faces)]
    surf_pid = [lp_base + 2 * k + 1 for k in range(n_faces)]
    F_START, F_END = 0, 1                       # face list slots

    def f_side(i: int) -> int:
        return 2 + i

    # --- face frames -------------------------------------------------------
    # start cap: origin = curve 0's end vertex V1 on the start plane,
    # xVec = curve-0 tangent, yVec = normal x xVec   [V]
    # end cap: same origin on the end plane, xVec = -tangent0    [V]
    # side_i: origin = Vi on the start plane, xVec = extrusion dir (down),
    # yVec = tangent_i                                            [V]
    frames = {}
    frames[F_START] = (top[1], tan[0], _cross(up, tan[0]))
    frames[F_END] = (bot[1], _neg(tan[0]), _cross(dn, _neg(tan[0])))
    for i in range(n):
        frames[f_side(i)] = (top[i], ext, tan[i])

    def to_uv(fslot: int, p3: Vec) -> List[float]:
        o, x, y = frames[fslot]
        d = _sub(_v(p3), o)
        return _uv([_dot(d, x), _dot(d, y)])

    def envelope(fslot: int, pts: Sequence[Vec]) -> List[List[float]]:
        uvs = [to_uv(fslot, p) for p in pts]
        us = [u for u, _ in uvs]
        vs_ = [w for _, w in uvs]
        return [[min(us), min(vs_)], [max(us), max(vs_)]]

    def face_pts(fslot: int):
        if fslot == F_START:
            return top
        if fslot == F_END:
            return bot
        i = fslot - 2
        return [top[i], top[(i + 1) % n], bot[(i + 1) % n], bot[i]]

    # --- edges -------------------------------------------------------------
    # rail_start[i]: Vi -> Vi+1 on the start plane, faces [start cap, side_i]
    # rail_end[i]  : Vi+1 -> Vi on the end plane,  faces [end cap,   side_i]
    # lateral[i] (i<n-1, at V(i+1)): bottom -> top, faces [side_(i+1), side_i]
    # closing lateral (at V0)      : top -> bottom, faces [side_0, side_(n-1)]
    E = {}                                   # tag -> edge record
    order: List[int] = []                    # edge tags in serialization order
    for i in range(n):
        order.append(tags["rail_start"][i]); order.append(tags["rail_end"][i])
    for i in range(n):
        order.append(tags["lateral"][i])
    order.sort()                             # tags 3,4,6,7,8,10,...  (pid order)
    epid = {tag: epid_base + k for k, tag in enumerate(order)}

    def lat_at_vertex(j: int) -> int:
        """tag of the lateral edge at vertex Vj (V0 = the closing lateral)."""
        return tags["lateral"][n - 1] if j == 0 else tags["lateral"][j - 1]

    for i in range(n):
        j = (i + 1) % n
        E[tags["rail_start"][i]] = dict(
            faces=[F_START, f_side(i)], p_first=top[i], p_last=top[j],
            flags=EDGE_FLAGS_FORWARD_IN_A)
        E[tags["rail_end"][i]] = dict(
            faces=[F_END, f_side(i)], p_first=bot[j], p_last=bot[i],
            flags=EDGE_FLAGS_FORWARD_IN_A)
    for i in range(n - 1):
        j = i + 1                                            # vertex V(i+1)
        E[tags["lateral"][i]] = dict(
            faces=[f_side(j), f_side(i)], p_first=bot[j], p_last=top[j],
            flags=EDGE_FLAGS_REVERSED_IN_A)
    E[tags["lateral"][n - 1]] = dict(                        # closing, at V0
        faces=[f_side(0), f_side(n - 1)], p_first=top[0], p_last=bot[0],
        flags=EDGE_FLAGS_FORWARD_IN_A)

    # --- per-face loop membership (cyclic order) ---------------------------
    loops: Dict[int, List[int]] = {}
    loops[F_START] = [tags["rail_start"][i] for i in range(n)]
    loops[F_END] = [tags["rail_end"][i] for i in reversed(range(n))]
    for i in range(n):
        loops[f_side(i)] = [tags["rail_start"][i], lat_at_vertex(i),
                            tags["rail_end"][i], lat_at_vertex((i + 1) % n)]

    def link(fslot: int, etag: int) -> Tuple[int, int]:
        """(next, prev) weak targets of edge ``etag`` inside face ``fslot``'s
        loop: the neighbouring edge pids, or the EdgeLoop's own pid for the
        first (prev) / last (next) edge of the chain. [V]"""
        seq = loops[fslot]
        k = seq.index(etag)
        nxt = epid[seq[k + 1]] if k + 1 < len(seq) else loop_pid[fslot]
        prv = epid[seq[k - 1]] if k > 0 else loop_pid[fslot]
        return nxt, prv

    # --- assemble faces ----------------------------------------------------
    face_defs = [(F_START, tags["start_face"], up), (F_END, tags["end_face"], dn)]
    for i in range(n):
        face_defs.append((f_side(i), tags["face"][i], None))
    faces_out = []
    for fslot, ftag, _nrm in face_defs:
        o, x, y = frames[fslot]
        env = envelope(fslot, face_pts(fslot))
        first_edge = epid[loops[fslot][0]]
        last_edge = epid[loops[fslot][-1]]
        lp = blank_object("EdgeLoop")
        lp["m_GInfo"] = ginfo(flags=LOOP_INFO_FLAGS)
        lp["m_nextLoop"] = None
        lp["m_pFace"] = _weak(fpid[fslot])
        lp["m_next"] = _weak(first_edge)
        lp["m_prev"] = _weak(last_edge)
        lp["m_Envelope"] = {"m_corners": [env[0], env[1]]}
        lp["m_open"] = False
        f = blank_object("Face")
        f["m_GInfo"] = ginfo(tag=ftag, flags=FACE_FLAGS)
        f["m_pFirstLoop"] = _ptr("EdgeLoop", lp, loop_pid[fslot])
        f["m_faceRegions"] = []
        f["m_pGFilling"] = None
        f["m_oBackgroundFilling"] = None
        f["m_renderStyleId"] = INVALID
        f["m_cutType"] = 0
        f["m_faceFlags_v9"] = 4
        surf = plane(o, x, y, env)
        surf["pid"] = surf_pid[fslot]
        f["m_pSurf"] = surf
        faces_out.append(_ptr("Face", f, fpid[fslot]))

    # --- assemble edges (pid order = tag order) -----------------------------
    edges_out = []
    for tag in order:
        d = E[tag]
        fa, fb = d["faces"]
        nxa, pva = link(fa, tag)
        nxb, pvb = link(fb, tag)
        e = blank_object("Edge")
        e["m_GInfo"] = ginfo(tag=tag, flags=EDGE_INFO_FLAGS)
        e["m_pFace"] = [_weak(fpid[fa]), _weak(fpid[fb])]
        e["m_next"] = [_weak(nxa), _weak(nxb)]
        e["m_prev"] = [_weak(pva), _weak(pvb)]
        e["m_interiorEdgePnts"] = []
        e["m_firstAndLastEdgePnts"] = [
            {"uv": [to_uv(fa, d["p_first"]), to_uv(fb, d["p_first"])]},
            {"uv": [to_uv(fa, d["p_last"]), to_uv(fb, d["p_last"])]},
        ]
        e["m_flags"] = int(d["flags"])
        edges_out.append(_ptr("Edge", e, epid[tag]))

    # --- Geometry + GElement root ------------------------------------------
    geom = blank_object("Geometry")
    geom["m_GInfo"] = ginfo(category=geometry_style_id, tag=-1,
                            control_command=control_command,
                            flags=GEOMETRY_FLAGS)
    geom["m_pFaces"] = faces_out
    geom["m_flags"] = 7
    geom["m_geometryTag"] = INVALID
    geom["m_tessEpsCntrl"] = {"m_type": 0, "m_TessEpsCntrlVersion": 1}
    geom["m_pEdges"] = edges_out
    geom["m_sharedSurfInfo"] = []

    pts = top + bot
    bbox = [[min(p[k] for p in pts) for k in range(3)],
            [max(p[k] for p in pts) for k in range(3)]]
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(tag=element_id, flags=GELEM_ROOT_FLAGS)
    root["m_subNodes"] = [_ptr("Geometry", geom, p_geometry)]
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_elementId"] = int(element_id)
    root["m_gElemType"] = 3
    root["m_flags"] = 0
    # self-check: the encoder's numbering must equal our formulaic pids
    _assert_pid_stable(root)
    return root


def _assert_pid_stable(obj: dict) -> None:
    """Re-run the archive numbering on a copy and assert every pointer /
    weakref target we set formulaically is what the encoder assigns."""
    a = copy.deepcopy(obj)
    assign_pids(a)
    if a != obj:
        raise AssertionError("constructor pid layout != archive numbering "
                             "(assign_pids disagrees)")


# ---------------------------------------------------------------------------
# gStep history tables + geometry table
# ---------------------------------------------------------------------------

def extrusion_gstep(n_curves: int, *, step_id: int = 1, flags: int = 0) -> dict:
    """The ExtrusionGStep of an n-curve profile extrusion: the face and edge
    history tables that name every face/edge of the solid by TAG. [V]

    faceHist keys: start cap [1,-1,-1], end cap [2,-1,-1], side of curve i
    [3,i,-1]; edgeHist keys: rails [1,i,0]/[1,i,1], laterals [2,i,j].
    """
    tags = _box_tags(n_curves)
    face_hist = [{"m_id": tags["start_face"], "m_faceHist": {"m_keys": [1, -1, -1]}},
                 {"m_id": tags["end_face"], "m_faceHist": {"m_keys": [2, -1, -1]}}]
    for i in range(n_curves):
        face_hist.append({"m_id": tags["face"][i],
                          "m_faceHist": {"m_keys": [3, i, -1]}})
    edge_hist = []
    for i in range(n_curves):
        edge_hist.append({"m_id": tags["rail_start"][i],
                          "m_edgeHist": {"m_keys": [1, i, 0, -1]}})
        edge_hist.append({"m_id": tags["rail_end"][i],
                          "m_edgeHist": {"m_keys": [1, i, 1, -1]}})
    for i in range(n_curves):
        j = (i + 1) % n_curves
        edge_hist.append({"m_id": tags["lateral"][i],
                          "m_edgeHist": {"m_keys": [2, i, j, -1]}})
    st = blank_object("ExtrusionGStep")
    st["m_faceHistTable"] = face_hist
    st["m_curveHistTableSet"] = []
    st["m_edgeHistTable"] = edge_hist
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = int(step_id)
    st["m_version"] = 0
    st["m_flags"] = int(flags)
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    return st


def _gstep_list(form_steps: list, non_brep_steps: list = None, *,
                latest: int = 2, id_counter: int = 2, flags: int = 9) -> dict:
    """A ``GeomStepList`` (m_latestGStepTypeInPrevRegenCycle: 2 = a form
    step, 1 = a sketch/curve step -- 5 identical entries)."""
    gl = blank_object("GeomStepList")
    gl["m_nonBRepGList"] = non_brep_steps or []
    gl["m_bRepFormGList"] = form_steps or []
    gl["m_bRepAdjustGList"] = []
    gl["m_bRepCutOutGList"] = []
    gl["m_bRepPostCutOutGList"] = []
    gl["m_bRepTweakGList"] = []
    gl["m_bRepFormSnapshot"] = None
    gl["m_bRepAdjustSnapshot"] = None
    gl["m_bRepCutOutSnapshot"] = None
    gl["m_bRepPostCutOutSnapshot"] = None
    gl["m_pElem"] = _weak(2)
    gl["m_latestGStepTypeInPrevRegenCycle"] = [latest] * 5
    gl["m_idCounter"] = int(id_counter)
    gl["m_flags"] = int(flags)
    return _ptr("GeomStepList", gl)


def _geom_table(n_tags: int, generator: int = 1) -> dict:
    gt = blank_object("GeomTable")
    gt["m_refPntMirrored"] = False
    gt["m_table"] = [{"m_geomGeneratorId": int(generator)} for _ in range(n_tags)]
    gt["m_bigTableOwner"] = None
    gt["m_materialMarkers"] = []
    gt["m_faceTypeMarkers"] = []
    return _ptr("GeomTable", gt)


def _cell_list(*cells) -> dict:
    return _ptr("CellList", {"m_cells": list(cells)})


def _pattern_helper() -> dict:
    return _owned("PatternHelper", m_PatternPositionMap=[], m_substituteFaceMap=[])


def _int_params(pairs: dict) -> dict:
    return _owned("ParamValueSetInt",
                  m_paramSet=[{"m_paramId": int(k), "m_value": int(v)}
                              for k, v in pairs.items()])


def _double_params(pairs: List[Tuple[int, float]]) -> dict:
    """ParamValueSetDouble in the given ORDER (extrusion: end, then start)."""
    return _owned("ParamValueSetDouble",
                  m_paramSet=[{"m_value": float(v), "m_paramId": int(k)}
                              for k, v in pairs])


# ---------------------------------------------------------------------------
# element constructors
# ---------------------------------------------------------------------------

def _hdr(cls: str, ctx: FamilyDocContext, elem_id: int, *, category: int = -1,
         deletion: Iterable[int], regen_only: Iterable[int] = (),
         appearance: Iterable[int] = (),
         nondeterm: bool = False, misc_id: int = INVALID,
         bbox: Optional[Sequence[Sequence[float]]] = None) -> dict:
    """seq-101 ElementHeader for a family FORM element (family-doc flags).

    ``misc_id`` -- CurveElem headers carry their SKETCH id here (both
    specimen documents; every other form class carries -1) [V].  ``bbox``
    -- an Outline; the standalone .rfa specimens carry one on VarSketch /
    CurveElem / ExtrusionElem headers (the embedded rme copies carry
    None; both load) [V].
    """
    ab, vis = ctx.hdr[cls]
    h = element_header(cls, category=category,
                       deletion=[i for i in deletion if i not in (None, INVALID)] + [elem_id],
                       regen_only=list(regen_only), appearance=list(appearance),
                       flags=ab, visible_view_flags=vis,
                       family_id=ctx.family_id, design_option=NO_DESIGN_OPTION,
                       misc_id=int(misc_id),
                       bbox=(list(map(list, bbox)) if bbox is not None else None))
    if nondeterm:
        h["m_parents"]["value"]["m_hasNonDetermRegenChildren"] = True
    return h


def _base(cls: str, elem_id: int, *, family_id: int, int_params=None,
          double_params_ordered=None) -> dict:
    """Blank ``cls`` object with the universal Element base fields set."""
    obj = blank_object(cls)
    element_defaults(obj, elem_id, int_params=int_params,
                     design_option=FAMILY_DESIGN_OPTION)
    if double_params_ordered is not None:
        obj["m_pParamValueSetDouble"] = _double_params(double_params_ordered)
    obj["m_famId"] = int(family_id)
    return obj


def new_sketch_plane(elem_id: int, ctx: FamilyDocContext, *, sketch_id: int,
                     z: float = 0.0, datum_id: Optional[int] = None,
                     trf3x3: Optional[Sequence[Sequence[float]]] = None,
                     origin: Optional[Sequence[float]] = None,
                     vec_in_plane: Optional[Sequence[float]] = None,
                     notes=None) -> SkelElement:
    """A ``SketchPlane`` ON a DATUM (``OnDatumPlaneRef.m_datumPlaneId``),
    by default the family's horizontal 'Ref. Level'.

    This is the family author's "pick the reference level as the sketch
    plane" and is what makes the profile follow the level datum -- the
    reference-plane-driven hook of a form. [V both specimens]

    ``datum_id`` points the sketch at a DIFFERENT datum -- a vertical
    ``RefPlane`` -- so the profile is drawn on that plane and the form
    extrudes along ITS normal instead of straight up.  That is the only way
    the part contract can express a body whose axis is not vertical: a wheel,
    an axle, a strut channel's own C-profile.  UNVERIFIED against Autodesk's
    reader: the sketch's 2D frame on a vertical plane, the transform below and
    the cached B-rep all have to agree, and only a desktop round can say they
    do (probe: experiments/ifc-assembly/rotate).
    """
    obj = _base("SketchPlane", elem_id, family_id=ctx.family_id)
    ref = blank_object("OnDatumPlaneRef")
    ref["m_geomRef"] = _geomref_blank()
    # OnDatumPlaneRef inherits m_vecInPlane from OneElementMovablePlaneRef: the
    # vector IN the plane that orients the sketch on it.  Zero is harmless on the
    # horizontal level (there is only one sensible frame) but says NOTHING on a
    # vertical RefPlane -- a candidate reason rounds 1 and 2 kept extruding up.
    ref["m_vecInPlane"] = ([0.0, 0.0, 0.0] if vec_in_plane is None
                           else [float(c) for c in vec_in_plane])
    ref["m_rotation"] = 0.0
    ref["m_datumPlaneId"] = int(ctx.level_id if datum_id is None else datum_id)
    ref["m_mirror"] = False
    obj["m_oPlaneRef"] = _ptr("OnDatumPlaneRef", ref)
    trf = blank_object("Trf")
    trf["m_3x3"] = ([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
                    if trf3x3 is None else [[float(c) for c in row] for row in trf3x3])
    trf["m_or"] = ([0.0, 0.0, float(z)] if origin is None
                   else [float(c) for c in origin])
    obj["m_oTrf"] = _ptr("Trf", trf)
    obj["m_userId"] = int(sketch_id)              # the VarSketch on this plane [V]
    obj["m_flipZ"] = False
    assign_pids(obj)
    datum = int(ctx.level_id if datum_id is None else datum_id)
    hdr = _hdr("SketchPlane", ctx, elem_id,
               deletion=[ctx.family_id, datum, sketch_id])
    return SkelElement(elem_id, "SketchPlane", hdr, obj, None, kind="sketch_plane",
                       owner_id=ctx.family_id,
                       refs={"level": datum, "sketch": sketch_id},
                       notes=list(notes or []))


def _geomref_blank() -> dict:
    g = blank_object("GeomRef")
    g["m_intermediateTags"] = []
    g["m_oNextRef"] = None
    g["m_elemId"] = INVALID
    g["m_ownerDBViewId"] = INVALID
    g["m_foreignElemIdRef"] = {"m_id64": INVALID}
    g["m_geomTag"] = -1
    g["m_subTag"] = -1
    g["m_famMemberIdx"] = -1
    g["m_flags"] = 0
    g["m_isLazyRef"] = False
    return g


def new_var_sketch(elem_id: int, ctx: FamilyDocContext, *, sketch_plane_id: int,
                   user_id: int, lines: Sequence[Tuple[Vec, Vec]],
                   curve_ids: Sequence[int], dim_ids: Sequence[int] = (),
                   notes=None) -> SkelElement:
    """The profile ``VarSketch``: ``lines`` = [(p0, p1), ...] as drawn
    (feet, in the sketch plane), ``curve_ids`` = the matching ``CurveElem``
    ids (same order), ``user_id`` = the ExtrusionElem this sketch feeds.

    Carries the absorbed curve copies + per-curve data, the sketch-curve
    regen step (one curveHist [1,i,-1,-1,-1] per curve), the curve->index
    maps and its rep (the same lines as G-lines).  Solver state
    (m_elemRecs / m_constrRecs / guess cache) is emitted EMPTY -- an
    unsolved-but-consistent sketch [H: Revit re-solves on edit].
    """
    n = len(lines)
    if n != len(curve_ids):
        raise ValueError("one CurveElem id per sketch line")
    obj = _base("VarSketch", elem_id, family_id=ctx.family_id)
    # regen step: RegenSketchCurvesGStep
    st = blank_object("RegenSketchCurvesGStep")
    st["m_faceHistTable"] = []
    st["m_curveHistTableSet"] = [{"m_id": i, "m_curveHist": {"m_keys": [1, i, -1, -1, -1]}}
                                 for i in range(n)]
    st["m_edgeHistTable"] = []
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = 1
    st["m_version"] = 0
    st["m_flags"] = 0
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    obj["m_geomSteps"] = _gstep_list([], [_ptr("RegenSketchCurvesGStep", st)],
                                     latest=1, id_counter=2, flags=1)
    obj["m_pGeomTable"] = _geom_table(n)
    grp = _owned("SketchGroupHelper",
                 m_pElemIdsPairSet=_owned("ElementIdIndexPairSet", m_data=[]),
                 m_nextIndex=0)
    obj["m_cellList"] = _cell_list(grp, _pattern_helper())
    obj["m_userId"] = -1
    obj["m_elemIdsPairSet"] = _owned("ElementIdIndexPairSet",
                                    m_data=[{"m_elementId": int(cid), "m_index": i}
                                            for i, cid in enumerate(curve_ids)])
    obj["m_pPointIdsPairSet"] = _owned("ElementIdIndexPairSet", m_data=[])
    obj["m_dimIds"] = [int(d) for d in dim_ids]
    obj["m_clineIds"] = []
    # the sketch's own plane (identity frame; envelope = the curves' extents)
    xs = [p[0] for a, b in lines for p in (a, b)]
    ys = [p[1] for a, b in lines for p in (a, b)]
    env = [[min(xs), min(ys)], [max(xs), max(ys)]]
    obj["m_pPlane"] = plane([0, 0, 0], [1, 0, 0], [0, 1, 0], env)
    obj["m_oSketchGridData"] = None
    obj["m_refPnt"] = None
    obj["m_sketchPlaneId"] = int(sketch_plane_id)
    # serFlags 32 + version 1 on a curve-bearing parametric sketch (donor
    # 2432; the curve-less donor sketch 2400 carries 1/0 -- 32 plausibly
    # flags the serialized solver state below)
    obj["m_serFlags"] = 32 if n else 1
    obj["m_nextIndex"] = n
    obj["m_isEdited"] = 0
    obj["m_version"] = 1 if n else 0
    obj["m_remainVisible"] = False
    obj["m_isSuspendedNew"] = False
    obj["m_allowResetLineEndConstr"] = True
    obj["m_isHostForReferenceLines"] = False
    obj["m_flipXY"] = False
    obj["m_flipZ"] = False
    obj["m_absorbedCurves"] = [gline_between(a, b, tag=i, flags=ctx.gline_flags)
                              for i, (a, b) in enumerate(lines)]
    obj["m_absorbedCurvesData"] = [
        _owned("CurveElemData", m_oUserData=None, m_oAssocProp=None)
        for _ in range(n)]
    obj["m_customDatumPlanes"] = []
    obj["m_pPlaneRef"] = None
    # SOLVER STATE (issue #333, desktop round 26 -- the value-edit law):
    # regen resolves each curve through VarSketch::getCurveObj, which indexes
    # m_elemRecs; an empty solver ("[H: Revit re-solves on edit]") is
    # FALSIFIED -- editing any family parameter raised "Invalid idx in
    # VarSketch::getCurveObj (VarSketch.cpp:634)" + the serious-error dialog.
    # Donor law (Revit-2026-born famdoc, VarSketch 2432): one
    # VarSketchLineSegObj per curve (4 VarParams = x1,y1,x2,y2), a HorVer
    # constraint per axis-parallel edge + point-point joins closing the
    # loop, and the guess cache primed with the parameter vector.
    # Weakrefs address solver objects by archive pid: pid 3 = m_pPlane,
    # 4..3+n = the absorbed GLines, 4+n+i = LineSegObj i (assign_pids
    # reproduces this numbering).
    seg_pid = [4 + n + i for i in range(n)]
    obj["m_elemRecs"] = [
        _ptr("VarSketchLineSegObj", {
            "m_params": [_ptr("VarParam", {"m_refCt": 1, "m_val": float(c)})
                         for c in (a[0], a[1], b[0], b[1])],
            "m_pSketch": _weak(2),
            "m_objId": int(curve_ids[i]),
            "m_angleCoef": 1.0,
            "m_unbounded": False,
        }) for i, (a, b) in enumerate(lines)]
    obj["m_curveObjIdxMap"] = [{"first": int(cid), "second": i}
                               for i, cid in enumerate(curve_ids)]
    obj["m_pointRecs"] = []
    obj["m_pointObjIdxMap"] = []

    def _hv(i: int, horizontal: bool) -> dict:
        return _ptr("VarSketchHorVerConstrObj", {
            "m_params": [], "m_pSketch": _weak(2), "m_objId": -1,
            "m_constrElems": [{"weakref": seg_pid[i]}],
            "m_constrSubTypes": [0], "m_priorityLevel": 3,
            "m_hor": bool(horizontal)})

    def _pp(i: int, j: int, sub_i: int, sub_j: int) -> dict:
        return _ptr("VarSketchPPConstrObj", {
            "m_params": [], "m_pSketch": _weak(2), "m_objId": -1,
            "m_constrElems": [{"weakref": seg_pid[i]}, {"weakref": seg_pid[j]}],
            "m_constrSubTypes": [sub_i, sub_j], "m_priorityLevel": 0})

    def _is_horizontal(a, b) -> bool:
        return abs(b[1] - a[1]) <= abs(b[0] - a[0])
    # PP joins are COINCIDENCE-DETECTED, not copied by index pattern: the
    # donor's subtype semantics are 1 = the (x1,y1) start, 2 = the (x2,y2)
    # end, and each PP names one shared CORNER (donor round 27: gluing the
    # wrong corners re-solves the loop into overlapping lines -> "Base
    # sketch for extrusion is invalid").  Interleave per donor: HV0, then
    # for each edge i>0 its joins to lower-index edges, then HV(i).
    def _corner_joins(i: int) -> list:
        out = []
        pts_i = (lines[i][0], lines[i][1])
        for j in range(i):
            pts_j = (lines[j][0], lines[j][1])
            for si, pi_ in enumerate(pts_i, start=1):
                for sj, pj in enumerate(pts_j, start=1):
                    if abs(pi_[0] - pj[0]) < 1e-9 and abs(pi_[1] - pj[1]) < 1e-9:
                        out.append(_pp(i, j, si, sj))
        return out
    constrs: list = []
    if n >= 2:
        constrs.append(_hv(0, _is_horizontal(*lines[0])))
        for i in range(1, n):
            constrs.extend(_corner_joins(i))
            constrs.append(_hv(i, _is_horizontal(*lines[i])))
    obj["m_constrRecs"] = constrs
    gc = blank_object("VarSketchGuessCache")
    gc["m_pSketch"] = _weak(2)
    gc["m_guessArr"] = [_ptr("VarSketchGuess", {
        "m_values": [float(c) for a, b in lines for c in (a[0], a[1], b[0], b[1])],
        "m_useCount": 29})]
    gc["m_nPar"] = 0
    obj["m_oGuessCache"] = _ptr("VarSketchGuessCache", gc)
    obj["m_oParamPlane"] = plane([0, 0, 0], [1, 0, 0], [0, 1, 0],
                                  [[1.0, 1.0], [0.0, 0.0]])
    obj["m_dimData"] = []
    obj["m_weakDimIds"] = []
    obj["m_autodimDisabled"] = False
    obj["m_isParametric"] = True
    obj["m_highResidualTol"] = False
    obj["m_userId"] = int(user_id)                # the extrusion this sketch feeds [V]
    assign_pids(obj)
    # rep: the sketch lines as a GElement of GLines (gElemType 2)
    rep = _sketch_rep(elem_id, lines, ctx.gline_flags + GLINE_REP_SKETCH_DELTA)
    hdr = _hdr("VarSketch", ctx, elem_id,
               deletion=[ctx.family_id, sketch_plane_id, user_id,
                         *curve_ids, *dim_ids],
               regen_only=[ctx.level_id])
    return SkelElement(elem_id, "VarSketch", hdr, obj, rep, kind="sketch",
                       owner_id=user_id,
                       refs={"sketch_plane": sketch_plane_id, "extrusion": user_id,
                             "curves": list(curve_ids)},
                       notes=list(notes or []))


def _sketch_rep(elem_id: int, lines, gline_flags: int) -> dict:
    """seq-103 GElement of a VarSketch: its lines as GLine sub-nodes."""
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(tag=elem_id, flags=GELEM_ROOT_FLAGS)
    root["m_subNodes"] = [gline_between(a, b, tag=-1, flags=gline_flags)
                          for (a, b) in lines]
    pts = [_v(p) for a, b in lines for p in (a, b)]
    bbox = [[min(p[k] for p in pts) for k in range(3)],
            [max(p[k] for p in pts) for k in range(3)]]
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_elementId"] = int(elem_id)
    root["m_gElemType"] = 2
    root["m_flags"] = 0
    assign_pids(root)
    return root


def new_curve_elem(elem_id: int, ctx: FamilyDocContext, *, sketch_plane_id: int,
                   sketch_id: int, extrusion_id: int, p0: Vec, p1: Vec,
                   prev_id: int, next_id: int, tag: int = 0,
                   notes=None) -> SkelElement:
    """One profile line as a model ``CurveElem`` (category OST_Lines) with
    its driver ``GLine``, membership in the sketch and endpoint joins to
    its two neighbours (this line's end 0 = p0 meets ``prev_id``'s end 1,
    its end 1 = p1 meets ``next_id``'s end 0). [V]"""
    obj = _base("CurveElem", elem_id, family_id=ctx.family_id,
                int_params={BIP_CURVE_ELEM_INT: 1})
    st = blank_object("CurveElemGStep")
    st["m_faceHistTable"] = []
    st["m_curveHistTableSet"] = [{"m_id": 0, "m_curveHist": {"m_keys": [2, 0, -1, -1, -1]}}]
    st["m_edgeHistTable"] = []
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = 1
    st["m_version"] = 0
    st["m_flags"] = 0
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    obj["m_geomSteps"] = _gstep_list([], [_ptr("CurveElemGStep", st)],
                                     latest=1, id_counter=2, flags=1)
    obj["m_pGeomTable"] = _geom_table(1)
    obj["m_cellList"] = _cell_list(
        _owned("SketchMembership", m_groupId=int(sketch_id)), _pattern_helper())
    drv = blank_object("CurveElemDriver")
    drv["m_oControlData"] = None
    drv["m_pCrv"] = gline_between(p0, p1, tag=int(tag), flags=ctx.gline_flags)
    drv["m_sideJoins"] = []
    drv["m_controlJoinsSet"] = [
        _join_entry(0, [(elem_id, 0), (prev_id, 1)]),
        _join_entry(1, [(elem_id, 1), (next_id, 0)]),
    ]
    drv["m_midParams"] = []
    drv["m_nextMidParamId"] = 4
    drv["m_flip"] = False
    drv["m_sideAlignments"] = []
    obj["m_pCurveDriver"] = _ptr("CurveElemDriver", drv)
    obj["m_data"] = {"m_oUserData": None, "m_oAssocProp": None}
    obj["m_oArcCntr"] = None
    obj["m_oEllipseElemData"] = None
    obj["m_categoryId"] = INVALID
    obj["m_sketchPlaneId"] = int(sketch_plane_id)
    obj["m_areaSchemeId"] = INVALID
    obj["m_zoneSchemeId"] = INVALID
    obj["m_famElemVisibility"] = {"m_flags": -1}
    obj["m_referenceType"] = 0
    obj["m_areaSeparation"] = False
    obj["m_bMEPSpaceSeparation"] = False
    obj["m_bMEPLoadAreaSeparation"] = False
    obj["m_isAreaMeasurementScheme"] = False
    obj["m_detail"] = False
    obj["m_showCenterMark"] = False
    obj["m_useOffsetPos"] = False
    assign_pids(obj)
    # rep: one GLine node (gElemType 2, root flags 32)
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(category=ctx.curve_style_id, tag=elem_id,
                             flags=GELEM_CURVE_ROOT_FLAGS)
    root["m_subNodes"] = [gline_between(p0, p1, tag=int(tag),
                                         flags=ctx.gline_flags + GLINE_REP_CURVE_DELTA)]
    a, b = _v(p0), _v(p1)
    bbox = [[min(a[k], b[k]) for k in range(3)], [max(a[k], b[k]) for k in range(3)]]
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_elementId"] = int(elem_id)
    root["m_gElemType"] = 2
    root["m_flags"] = 32
    assign_pids(root)
    # header: CurveElem headers carry their sketch id in m_miscId and set
    # m_hasNonDetermRegenChildren, in BOTH specimen documents [V]
    hdr = _hdr("CurveElem", ctx, elem_id, category=BIC_LINES,
               deletion=[ctx.family_id, sketch_plane_id, sketch_id, prev_id, next_id],
               appearance=[sketch_id], regen_only=[ctx.level_id, extrusion_id],
               nondeterm=True, misc_id=sketch_id, bbox=None)  # donor law #52: headers carry no bbox
    return SkelElement(elem_id, "CurveElem", hdr, obj, root, kind="curve",
                       owner_id=sketch_id,
                       refs={"sketch": sketch_id, "sketch_plane": sketch_plane_id,
                             "prev": prev_id, "next": next_id},
                       notes=list(notes or []))


def _join_entry(index: int, ends: List[Tuple[int, int]]) -> dict:
    """One CurveElemDriver.m_controlJoinsSet entry: a join at end ``index``
    (0 = start point, 1 = end point) with the (elemId, joinedEnd) pairs."""
    # m_JoinInfo is an inline value struct (key order = wire order) [V]
    info = {"m_cleanData": {"m_data": []},
            "m_info": [{"m_elemId": int(e), "m_joinedEnd": int(j), "m_bTangent": False}
                       for e, j in ends],
            "m_wallJoinType": 0}
    return {"m_JoinInfo": info, "m_index": int(index)}


def new_extrusion(elem_id: int, ctx: FamilyDocContext, *, sketch_id: int,
                  sketch_plane_id: int, profile: RectProfile | Sequence[Vec],
                  start: float, end: float, rep: str = REP_SOLID,
                  category_id: int = INVALID, material_id: int = INVALID,
                  notes=None,
                   always_ref_plane_norm: bool = False) -> SkelElement:
    """The ``ExtrusionElem`` form: start/end offsets (params -1001800 /
    -1001801, feet along the sketch normal), the ExtrusionGStep tag map,
    the per-tag geometry table, its private copy of the traced profile
    loop, and the seq-103 rep -- ``rep='solid'`` = our authored six-face
    B-rep, ``rep='dummy'`` = SerializedDummy (regeneration test, F4).
    """
    prof = profile if isinstance(profile, RectProfile) else profile_from_vertices(profile)
    V = [_v(p) for p in prof.vertices]
    n = len(V)
    if not float(start) > float(end):
        raise ValueError("extrusions here are extrude-DOWN: start > end")
    obj = _base("ExtrusionElem", elem_id, family_id=ctx.family_id,
                int_params={BIP_CURVE_ELEM_INT: 1},
                double_params_ordered=[
                    # Revit reads -1001800 as "Extrusion Start" and -1001801
                    # as "Extrusion End", and shows Depth = End - Start.  The
                    # box path traces extrude-DOWN (its `start` IS the top),
                    # so writing the raw pair put the top in Start and gave
                    # every box a NEGATIVE depth in the properties palette
                    # [owner screenshot: Start 0'5 3/4", End 0'0",
                    # Depth -0'5 3/4"].  Order by elevation, not by the
                    # tracer's direction; the B-rep is unaffected.
                    (BIP_EXTRUSION_END, max(float(start), float(end))),
                    (BIP_EXTRUSION_START, min(float(start), float(end)))])
    step = extrusion_gstep(n)
    obj["m_geomSteps"] = _gstep_list([_ptr("ExtrusionGStep", step)],
                                     latest=2, id_counter=2, flags=9)
    obj["m_pGeomTable"] = _geom_table(_box_tags(n)["count"])
    # the traced closed loop: curve i from Vi to Vi+1, anchored at its END
    # vertex with a [-len, 0] interval (Revit's traced-loop form). [V]
    loop_curves = [gline_between(V[i], V[(i + 1) % n], tag=i, anchor="end",
                                flags=ctx.gline_flags) for i in range(n)]
    cl = blank_object("CurveLoop")
    cl["m_open"] = False
    cl["m_curves"] = loop_curves
    helper = _owned("ExtrusionElemExtrusionHelper", m_sketchId=int(sketch_id),
                    m_complete=True, m_pCurveLoops=[_ptr("CurveLoop", cl)])
    obj["m_cellList"] = _cell_list(
        helper, _owned("GenSweepPatternHelper", m_PatternPositionMap=[],
                       m_substituteFaceMap=[]))
    obj["m_categoryId"] = int(category_id)        # sub-category (-1 = family category)
    obj["m_materialId"] = int(material_id)
    obj["m_famElemVisibility"] = {"m_flags": int(ctx.fam_elem_visibility)}
    obj["m_cutting"] = False
    obj["m_alwaysRefPlaneNorm"] = bool(always_ref_plane_norm)
    obj["m_sideRefPlaneCurveBased"] = False
    assign_pids(obj)
    if rep == REP_SOLID:
        solid = solid_box_brep(prof, start, end, element_id=elem_id,
                               geometry_style_id=ctx.geometry_style_id,
                               control_command=ctx.solid_control_command)
        # never ship an open or self-inconsistent shell again: the record
        # validator cannot see B-rep topology, so a broken solid used to
        # reach Revit with "0 errors" reported (issue #504).
        _probs = check_solid(solid, expect_n=len(prof.vertices))
        if _probs:
            raise ValueError("generated solid is not a closed manifold: "
                             + "; ".join(_probs))
    elif rep == REP_DUMMY:
        solid = None
    else:
        raise ValueError(f"rep must be {REP_SOLID!r} or {REP_DUMMY!r}")
    hdr = _hdr("ExtrusionElem", ctx, elem_id,
               deletion=[ctx.family_id, sketch_id],
               appearance=[ctx.family_id, sketch_id],
               regen_only=[*ctx.extra_regen_ids, sketch_plane_id])
    return SkelElement(elem_id, "ExtrusionElem", hdr, obj, solid, kind="extrusion",
                       owner_id=ctx.family_id,
                       refs={"sketch": sketch_id, "sketch_plane": sketch_plane_id,
                             "params": {"start_ft": float(start), "end_ft": float(end)}},
                       notes=list(notes or []))


# ---------------------------------------------------------------------------
# the FORM bundle: sketch plane + sketch + curve elems + extrusion
# ---------------------------------------------------------------------------

@dataclass
class FormBundle:
    """One authored form = its cluster of elements, in id order."""
    kind: str
    elements: List[SkelElement]
    params: dict = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)

    @property
    def ids(self) -> List[int]:
        return [e.elem_id for e in self.elements]

    def by_class(self, name: str) -> List[SkelElement]:
        return [e for e in self.elements if e.class_name == name]

    def roundtrip(self) -> dict:
        """Encode -> decode -> re-encode every record of every element."""
        rep = {}
        ok = True
        for e in self.elements:
            r = e.roundtrip()
            rep[e.elem_id] = {"class": e.class_name, "ok": r["ok"],
                              "detail": {k: v for k, v in r.items() if k != "ok"}}
            ok = ok and r["ok"]
        return {"ok": ok, "elements": rep}

    def to_json(self) -> dict:
        return {"kind": self.kind, "params": self.params, "notes": self.notes,
                "elements": [e.to_json() for e in self.elements]}


def _alloc(ids: Any) -> int:
    if hasattr(ids, "next"):
        return int(ids.next())
    if hasattr(ids, "next_id"):
        return int(ids.next_id())
    raise TypeError("ids must provide next() or next_id()")


def prism_form(profile: RectProfile, height_ft: float, ctx: FamilyDocContext,
               ids: Any, *, base_z_ft: float = 0.0, rep: str = REP_SOLID,
               kind: str = "prism", material_id: int = INVALID,
               category_id: int = INVALID) -> FormBundle:
    """The complete element cluster of a rectangular extrusion of ``profile``
    from z = base_z (end plane) up to z = base_z + height (start plane),
    sketched on the 'Ref. Level' datum plane.  7 elements: SketchPlane,
    VarSketch, 4 CurveElem, ExtrusionElem.  ``ids`` = any id allocator.
    """
    if height_ft <= 0:
        raise ValueError("height must be positive")
    V = profile.vertices
    n = len(V)
    id_plane = _alloc(ids)
    id_sketch = _alloc(ids)
    id_curves = [_alloc(ids) for _ in range(n)]
    id_extrusion = _alloc(ids)
    start = float(base_z_ft) + float(height_ft)     # top (start cap)
    end = float(base_z_ft)                          # bottom (end cap)
    lines = [(V[i], V[(i + 1) % n]) for i in range(n)]   # drawn CCW, head-to-tail
    elems: List[SkelElement] = []
    elems.append(new_sketch_plane(id_plane, ctx, sketch_id=id_sketch))
    elems.append(new_var_sketch(id_sketch, ctx, sketch_plane_id=id_plane,
                                user_id=id_extrusion, lines=lines, curve_ids=id_curves))
    for i in range(n):
        p0, p1 = lines[i]
        elems.append(new_curve_elem(
            id_curves[i], ctx, sketch_plane_id=id_plane, sketch_id=id_sketch,
            extrusion_id=id_extrusion, p0=p0, p1=p1,
            prev_id=id_curves[(i - 1) % n], next_id=id_curves[(i + 1) % n], tag=0))
    elems.append(new_extrusion(id_extrusion, ctx, sketch_id=id_sketch,
                               sketch_plane_id=id_plane, profile=profile,
                               start=start, end=end, rep=rep,
                               material_id=material_id, category_id=category_id))
    params = {"width_ft": profile.width, "depth_ft": profile.depth,
              "height_ft": float(height_ft), "base_z_ft": float(base_z_ft),
              "start_ft": start, "end_ft": end, "center": profile.center(),
              "rep": rep, "vertices": [list(v) for v in V]}
    notes = [
        "profile: 4 model CurveElems (OST_Lines) drawn CCW head-to-tail in a "
        "VarSketch on a SketchPlane whose datum is the family's Ref. Level",
        "ExtrusionElem params: -1001800 start (top) / -1001801 end (bottom), "
        "feet along the sketch normal (extrude-down: start > end)",
        ("rep=solid: cached six-face B-rep authored by solid_box_brep"
         if rep == REP_SOLID else
         "rep=dummy: SerializedDummy -- Revit must regenerate the solid on load (F4b)"),
        "solver state (VarSketch.m_elemRecs/m_constrRecs/guess cache) left EMPTY [H]",
    ]
    return FormBundle(kind, elems, params, notes)


def box(width_ft: float, depth_ft: float, height_ft: float,
        ctx: FamilyDocContext, ids: Any, *, base_z_ft: float = 0.0,
        center: Vec = (0.0, 0.0), rep: str = REP_SOLID,
        material_id: int = INVALID, category_id: int = INVALID) -> FormBundle:
    """A rectangular BOX form: width (x) x depth (y) x height (z), centred
    at ``center`` in plan, from z = base_z to z = base_z + height.

    E.g. a panelboard backbox from catalog facts (Feist: dimensions are
    facts) -- ``box(inches(20), inches(5.75), inches(48), ctx, ids)``.
    """
    prof = rect_profile(width_ft, depth_ft, center=center)
    return prism_form(prof, height_ft, ctx, ids, base_z_ft=base_z_ft, rep=rep,
                      kind="box", material_id=material_id, category_id=category_id)


def plate(width_ft: float, height_ft: float, thickness_ft: float,
          ctx: FamilyDocContext, ids: Any, *, base_z_ft: float = 0.0,
          center: Vec = (0.0, 0.0), rep: str = REP_SOLID) -> FormBundle:
    """A flat PLATE / faceplate: width x height in plan, ``thickness`` deep
    (a thin box; the panel dead-front / trim of a piece of gear)."""
    prof = rect_profile(width_ft, height_ft, center=center)
    return prism_form(prof, thickness_ft, ctx, ids, base_z_ft=base_z_ft, rep=rep,
                      kind="plate")


faceplate = plate


def polygon_cylinder(radius_ft: float, height_ft: float, ctx: FamilyDocContext,
                     ids: Any, *, base_z_ft: float = 0.0, center: Vec = (0.0, 0.0),
                     rep: str = REP_DUMMY, segments: int = 4) -> FormBundle:
    """A polygonal APPROXIMATION of a cylinder (an inscribed 4-gon prism)
    kept from the first delivery; :func:`cylinder` is the true arc-profile
    cylinder now."""
    r = float(radius_ft)
    if segments != 4:
        raise NotImplementedError("polygonal cylinder approximation is a 4-gon")
    cx, cy = float(center[0]), float(center[1])
    verts = [[cx + r, cy, 0.0], [cx, cy + r, 0.0], [cx - r, cy, 0.0], [cx, cy - r, 0.0]]
    prof = profile_from_vertices(verts)
    fb = prism_form(prof, height_ft, ctx, ids, base_z_ft=base_z_ft, rep=rep,
                    kind="cylinder(polygon)")
    fb.notes.append(f"circle of radius {r} ft approximated by an inscribed 4-gon")
    fb.params.update({"radius_ft": r, "approximation": "inscribed square"})
    return fb


# ---------------------------------------------------------------------------
# ARC profiles / CYLINDERS (docs/writer/family-geometry.md sec. 4)
#
# Ground truth: the sample .rfa's four-cylindrical-legs extrusion (element
# 614: 4 circles x 2 half-arcs, one solid of 10 faces / 24 edges) and its
# sketch 613 + arc CurveElems (3736/3741...).  Everything below reproduces
# that specimen's structure (see reproduce_specimen_cylinders).
# ---------------------------------------------------------------------------

#: Edge.m_GInfo.m_flags of the STRAIGHT SEAM (lateral) edges of a
#: cylindrical solid (the curved rails keep EDGE_INFO_FLAGS 557572) [V]
EDGE_SEAM_INFO_FLAGS = 557796
#: Edge.m_flags bit 3 = curved edge (curved rails carry 14 = 8 | 6) [V]
EDGE_FLAG_CURVED_BIT = 8
EDGE_FLAGS_CURVED_FORWARD_IN_A = EDGE_FLAG_CURVED_BIT | EDGE_FLAGS_FORWARD_IN_A   # 14
#: Geometry.m_flags: 7 on the two (all-planar) box specimens, 6 on both
#: rfa solids that contain curved faces (the fillet top 82 and the legs
#: 614) [V observed 4/4 -- bit0 clear when curved surfaces are present, H
#: semantics]
GEOMETRY_FLAGS_PLANAR = 7
GEOMETRY_FLAGS_CURVED = 6
#: curved-rail tessellation: the half-arc drawn as params [-pi, 0] (theta
#: frame [pi, 2pi], traversed FIRST) is stored with 6 uniform interior
#: points = 7 chords; its partner half [0, pi] with 5 interior points = 6
#: chords.  Deterministic on all 8 half-arcs of specimen 614 (radius
#: 0.125 ft) [V]; mechanism (why 7 vs 6 for equal spans) [H].
ARC_CHORDS_FIRST_HALF = 7
ARC_CHORDS_SECOND_HALF = 6


def cylsurf(center: Vec, radius: float, theta0: float, theta1: float,
            length: float, *, orient: bool = True) -> dict:
    """An owned ``CylSurf`` token: axis base ``center`` (at the START
    plane), angle frame xVec=+x / yVec=+y / zVec=+z (theta measured from
    +x, CCW), envelope [[theta0, 0], [theta1, length]] in (theta, v).
    ``CylSurf`` is NOT a registered class (pid stays -1) [V]."""
    v = blank_object("CylSurf")
    v["m_Envelope"] = {"m_corners": [_uv([theta0, 0.0]), _uv([theta1, length])]}
    v["m_orientFlag"] = bool(orient)
    v["m_center"] = _cv(_v(center))
    v["m_xVec"] = [1.0, 0.0, 0.0]
    v["m_yVec"] = [0.0, 1.0, 0.0]
    v["m_zVec"] = [0.0, 0.0, 1.0]
    v["m_radius"] = float(radius)
    return _ptr("CylSurf", v)


def arc_center_marker(center: Vec, *, tag: int = 1,
                      flags: int = GLINE_FLAGS_RFA) -> dict:
    """``CurveElem.m_oArcCntr``: the arc's centre marker -- a zero-length
    GLine at the centre pointing along the sketch normal, geometry tag 1
    (the arc itself is tag 0) [V rfa arc CurveElems 3736/3741]."""
    v = blank_object("GLine")
    v["m_GInfo"] = ginfo(tag=tag, flags=flags)
    v["m_endParams"] = [0.0, 0.0]
    v["m_origin"] = _cv(_v(center))
    v["m_dirVec"] = [0.0, 0.0, 1.0]
    return _ptr("GLine", v)


@dataclass
class CircleProfile:
    """A circle in the sketch plane, expressed the way Revit sketches one:
    TWO half arcs about the same centre -- the "upper" half U with params
    [0, pi] (drawn first, sketch curve index 0) and the "lower" half L with
    params [-pi, 0] (drawn second, index 1).  The extrusion tracer walks
    the closed loop starting at L: traversal = (L, U); the loop's frame
    vertex V1 = the theta=0 point (L's END), V0 = the theta=pi point [V]."""
    center: List[float]          # [x, y, 0]
    radius: float

    ANG_U = (0.0, math.pi)       # params of the upper half arc
    ANG_L = (-math.pi, 0.0)      # params of the lower half arc

    def point(self, theta: float, z: float = 0.0) -> List[float]:
        return [_clean(self.center[0] + self.radius * math.cos(theta)),
                _clean(self.center[1] + self.radius * math.sin(theta)),
                _clean(z)]

    @property
    def v0(self) -> List[float]:      # theta = pi vertex (left point)
        return self.point(math.pi)

    @property
    def v1(self) -> List[float]:      # theta = 0 vertex (right point)
        return self.point(0.0)


def circle_profile(center_xy: Vec, radius_ft: float) -> CircleProfile:
    if radius_ft <= 0:
        raise ValueError("radius must be positive")
    return CircleProfile([float(center_xy[0]), float(center_xy[1]), 0.0], float(radius_ft))


def _circle_loop_tags(base: int) -> dict:
    """Geometry-history TAG block of ONE two-arc circle loop whose traversal
    is (L, U): the box formula (:func:`_box_tags`) for a 2-curve loop
    starting at global tag ``base`` (the caps 0/1 are the solid's) [V]::

        side(L)=base, rail_top(L)=base+1, rail_bot(L)=base+2,
        side(U)=base+3, rail_top(U)=base+4, rail_bot(U)=base+5,
        lateral at V1 [2,L,U] = base+6, closing lateral at V0 [2,U,L] = base+7
    """
    return {"side_L": base, "rail_top_L": base + 1, "rail_bot_L": base + 2,
            "side_U": base + 3, "rail_top_U": base + 4, "rail_bot_U": base + 5,
            "lat_v1": base + 6, "lat_v0": base + 7}


def extrusion_gstep_circles(n_circles: int, *, step_id: int = 1, flags: int = 0,
                            tag_bases: Optional[Sequence[int]] = None) -> dict:
    """ExtrusionGStep for an extrusion of ``n_circles`` two-arc circle
    loops with a CLEAN sketch history: circle j's drawn curves are U = 2j
    and L = 2j+1; the traced loop is (L, U); tags per
    :func:`_circle_loop_tags` with base_j = 2 + 8j [V pattern of 614]."""
    face_hist = [{"m_id": 1, "m_faceHist": {"m_keys": [1, -1, -1]}},
                 {"m_id": 0, "m_faceHist": {"m_keys": [2, -1, -1]}}]
    edge_hist = []
    for j in range(n_circles):
        base = int(tag_bases[j]) if tag_bases else 2 + 8 * j
        t = _circle_loop_tags(base)
        cu, cl = 2 * j, 2 * j + 1               # drawn curve (history) indices
        face_hist.append({"m_id": t["side_L"], "m_faceHist": {"m_keys": [3, cl, -1]}})
        face_hist.append({"m_id": t["side_U"], "m_faceHist": {"m_keys": [3, cu, -1]}})
        edge_hist += [
            {"m_id": t["rail_top_L"], "m_edgeHist": {"m_keys": [1, cl, 0, -1]}},
            {"m_id": t["rail_bot_L"], "m_edgeHist": {"m_keys": [1, cl, 1, -1]}},
            {"m_id": t["rail_top_U"], "m_edgeHist": {"m_keys": [1, cu, 0, -1]}},
            {"m_id": t["rail_bot_U"], "m_edgeHist": {"m_keys": [1, cu, 1, -1]}},
            {"m_id": t["lat_v1"], "m_edgeHist": {"m_keys": [2, cl, cu, -1]}},
            {"m_id": t["lat_v0"], "m_edgeHist": {"m_keys": [2, cu, cl, -1]}},
        ]
    st = blank_object("ExtrusionGStep")
    st["m_faceHistTable"] = face_hist
    st["m_curveHistTableSet"] = []
    st["m_edgeHistTable"] = edge_hist
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = int(step_id)
    st["m_version"] = 0
    st["m_flags"] = int(flags)
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    return st


def _sym(key: str) -> dict:
    """A symbolic weakref placeholder resolved by :func:`_number_graph`."""
    return {"weakref_sym": key}


def _number_graph(root: dict, registry: Dict[str, dict]) -> None:
    """Assign archive object indices to ``root`` (:func:`assign_pids`) and
    resolve every ``{"weakref_sym": key}`` placeholder to
    ``{"weakref": registry[key]["pid"]}``.  Lets a constructor build a
    pointer graph without hand-computing the numbering (multi-loop solids)."""
    assign_pids(root)

    def resolve(v: Any) -> None:
        if isinstance(v, dict):
            for k, x in list(v.items()):
                if isinstance(x, dict) and "weakref_sym" in x:
                    v[k] = _weak(registry[x["weakref_sym"]]["pid"])
                else:
                    resolve(x)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, dict) and "weakref_sym" in x:
                    v[i] = _weak(registry[x["weakref_sym"]]["pid"])
                else:
                    resolve(x)

    resolve(root)



#: Fields of a cached B-rep that hold a POSITION (rotated about the pivot) and
#: those that hold a DIRECTION (rotated in place).  Measured on the authored
#: cylinder rep: m_xVec / m_yVec / m_zVec / m_origin / m_center and nothing else.
_REP_POSITION_FIELDS = ("m_origin", "m_center")
_REP_DIRECTION_FIELDS = ("m_xVec", "m_yVec", "m_zVec")


def rotate_rep(value: Any, rot: Sequence[Sequence[float]],
               pivot: Sequence[float] = (0.0, 0.0, 0.0),
               translate: Sequence[float] = (0.0, 0.0, 0.0)) -> Any:
    """Rotate an authored cached B-rep in place by the 3x3 ``rot`` about
    ``pivot`` (issue #591, rotation round 4).

    Three rounds established that NOTHING in the sketch changes what Revit
    draws for a form: not the sketch plane's datum, not
    ``ExtrusionElem.m_alwaysRefPlaneNorm``, not ``OnDatumPlaneRef.m_vecInPlane``.
    The remaining explanation is that the CACHED B-REP is what renders -- and
    ``cyl_surf`` hard-writes ``m_zVec = [0, 0, 1]``, so every cylinder we have
    ever authored says "vertical" in world coordinates no matter what its
    sketch says.

    This rotates the rep's positions and directions together, so a cylinder
    B-rep can lie on its side.  It deliberately does NOT touch the sketch: if
    the rotated body appears, the B-rep drives the display and the parametric
    side must then be made to agree (or the form regenerates back to vertical
    on the first edit -- a trade to measure, not to assume).
    """
    def rot3(v, translate_pos):
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        if translate:
            x -= pivot[0]; y -= pivot[1]; z -= pivot[2]
        out = [rot[i][0] * x + rot[i][1] * y + rot[i][2] * z for i in range(3)]
        if translate_pos:
            out = [out[i] + pivot[i] + translate[i] for i in range(3)]
        return out

    def walk(v):
        if isinstance(v, dict):
            for k, x in list(v.items()):
                if (isinstance(x, list) and len(x) == 3
                        and all(isinstance(n, (int, float)) for n in x)):
                    if k in _REP_POSITION_FIELDS:
                        v[k] = rot3(x, True)
                        continue
                    if k in _REP_DIRECTION_FIELDS:
                        v[k] = rot3(x, False)
                        continue
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(value)
    return value

def solid_cylinder_brep(circles: Sequence[CircleProfile], start: float, end: float,
                        *, element_id: int, geometry_style_id: int = -1,
                        control_command: int = 0,
                        tag_bases: Optional[Sequence[int]] = None,
                        u_shifts: Optional[Sequence[float]] = None,
                        render_style_id: int = INVALID,
                        tess_version: int = 0) -> dict:
    """The cached B-rep solid (seq-103 ``GElement``) of an extrusion whose
    profile is one or more two-arc circles ("cylinders in one extrusion").

    Built field by field per the topology decoded from the sample .rfa's
    four-leg extrusion 614 (docs/writer/family-geometry.md sec. 4): a top
    and a bottom cap ``Face`` (Plane surfaces, one ``EdgeLoop`` per circle
    chained by ``m_nextLoop``), two ``CylSurf`` half-cylinder faces per
    circle, and 6 edges per circle -- 4 curved rails (with the specimen's
    deterministic interior tessellation, 7 chords for the first half-arc /
    6 for the second) + 2 straight seam laterals.

    ``circles`` -- the loops (each 2 half-arcs, traversal L then U);
    ``start``/``end`` -- offsets along the sketch normal with ``end >
    start`` (extrude-UP, the only cylinder frame the corpus shows: the END
    cap is the top and is serialized first);  ``tag_bases`` -- per-circle
    history-tag block base (default clean history 2 + 8j; the specimen
    carries editing-history bases 114/122/130/138);  ``u_shifts`` -- the
    per-circle theta offset of the U face's frame (0 -> [0, pi]; the
    specimen also shows 2pi -> [2pi, 3pi]; both are valid, the choice is
    the tracer's) [V structure].
    """
    C = list(circles)
    k = len(C)
    if k < 1:
        raise ValueError("need at least one circle")
    zs, ze = float(start), float(end)
    if not ze > zs:
        raise ValueError("cylinders here are extrude-UP: require end > start "
                         "(the end cap is the top; the only specimen frame)")
    length = ze - zs
    bases = [int(b) for b in (tag_bases or [2 + 8 * j for j in range(k)])]
    shifts = [float(s) for s in (u_shifts or [0.0] * k)]
    tags = [_circle_loop_tags(b) for b in bases]
    TWO_PI = 2.0 * math.pi

    # --- symbolic object registry (pids resolved by _number_graph) ---------
    reg: Dict[str, dict] = {}

    def reg_ptr(key: str, cls: str, value: dict) -> dict:
        p = _ptr(cls, value)
        reg[key] = p
        return p

    # --- cap frames --------------------------------------------------------
    # origin = V1 (theta=0 point) of circle 0 lifted to the cap plane;
    # top cap: xVec = +y (the CCW tangent at V1), yVec = (+z) x xVec = -x;
    # bottom cap: xVec = -y, yVec = (-z) x xVec = -x  (outward normals) [V]
    o_top = C[0].point(0.0, ze)
    o_bot = C[0].point(0.0, zs)
    x_top, y_top = [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]
    x_bot, y_bot = [0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]

    def uv_top(p: Vec) -> List[float]:
        d = _sub(_v(p), o_top)
        return _uv([_dot(d, x_top), _dot(d, y_top)])

    def uv_bot(p: Vec) -> List[float]:
        d = _sub(_v(p), o_bot)
        return _uv([_dot(d, x_bot), _dot(d, y_bot)])

    def cap_env(uvfun) -> List[List[float]]:
        # analytic circle extents in the cap frame (the specimen's cache
        # envelopes deviate by ~1e-4 ft where a chord misses the extreme --
        # cache noise, docs sec. 4.4)
        us, vs = [], []
        for c in C:
            for th in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi):
                u, w = uvfun(c.point(th))
                us.append(u); vs.append(w)
        return [_uv([min(us), min(vs)]), _uv([max(us), max(vs)])]

    def circle_cap_env(c: CircleProfile, uvfun) -> List[List[float]]:
        us, vs = [], []
        for th in (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi):
            u, w = uvfun(c.point(th))
            us.append(u); vs.append(w)
        return [_uv([min(us), min(vs)]), _uv([max(us), max(vs)])]

    # --- per-circle theta frames + tessellation ----------------------------
    def theta_L(theta_world: float) -> float:
        """world angle -> the L face's parametric theta in [pi, 2pi]."""
        t = theta_world % TWO_PI
        return t + TWO_PI if t < math.pi - 1e-12 else t

    def theta_U(theta_world: float, s: float) -> float:
        """world angle -> the U face's parametric theta in [s, s+pi]."""
        return (theta_world % TWO_PI) + s

    node_pts: List[List[float]] = []          # every stored edge node (bbox)

    # --- faces ---------------------------------------------------------------
    F_TOP, F_BOT = "f_top", "f_bot"
    faces_out: List[dict] = []

    def make_face(key: str, ftag: int, first_loop: dict, surf: dict) -> dict:
        f = blank_object("Face")
        f["m_GInfo"] = ginfo(tag=ftag, flags=FACE_FLAGS)
        f["m_pFirstLoop"] = first_loop
        f["m_faceRegions"] = []
        f["m_pGFilling"] = None
        f["m_oBackgroundFilling"] = None
        f["m_renderStyleId"] = int(render_style_id)
        f["m_cutType"] = 0
        f["m_faceFlags_v9"] = 4
        f["m_pSurf"] = surf
        return reg_ptr(key, "Face", f)

    def make_loop(key: str, face_key: str, first_edge_key: str, last_edge_key: str,
                  env: List[List[float]], next_loop: Optional[dict] = None) -> dict:
        lp = blank_object("EdgeLoop")
        lp["m_GInfo"] = ginfo(flags=LOOP_INFO_FLAGS)
        lp["m_nextLoop"] = next_loop
        lp["m_pFace"] = _sym(face_key)
        lp["m_next"] = _sym(first_edge_key)
        lp["m_prev"] = _sym(last_edge_key)
        lp["m_Envelope"] = {"m_corners": [env[0], env[1]]}
        lp["m_open"] = False
        return reg_ptr(key, "EdgeLoop", lp)

    # per-circle edge role keys
    def ek(j: int, role: str) -> str:
        return f"e{j}_{role}"

    def fk_L(j: int) -> str:
        return f"f{j}_L"

    def fk_U(j: int) -> str:
        return f"f{j}_U"

    def lk(fkey: str) -> str:
        return f"loop_{fkey}"

    # cap loop chains (circle 0 first, chained via m_nextLoop) ------------------
    def cap_loops(cap_key: str, uvfun, first_of, last_of) -> dict:
        loops = []
        for j, c in enumerate(C):
            loops.append((f"loop_{cap_key}_{j}", circle_cap_env(c, uvfun), first_of(j), last_of(j)))
        head: Optional[dict] = None
        for (key, env, first_e, last_e) in reversed(loops):
            head = make_loop(key, cap_key, first_e, last_e, env, next_loop=head)
        return head

    top_first = cap_loops(F_TOP, uv_top, lambda j: ek(j, "rail_top_L"), lambda j: ek(j, "rail_top_U"))
    bot_first = cap_loops(F_BOT, uv_bot, lambda j: ek(j, "rail_bot_U"), lambda j: ek(j, "rail_bot_L"))
    make_face(F_TOP, 0, top_first, plane(o_top, x_top, y_top, cap_env(uv_top)))
    make_face(F_BOT, 1, bot_first, plane(o_bot, x_bot, y_bot, cap_env(uv_bot)))
    faces_out += [reg[F_TOP], reg[F_BOT]]

    # side faces (L then U per circle, tag order) --------------------------
    for j, c in enumerate(C):
        s = shifts[j]
        tj = tags[j]
        env_L = [[math.pi, 0.0], [TWO_PI, length]]
        env_U = [_uv([s, 0.0]), _uv([s + math.pi, length])]
        loop_L = make_loop(lk(fk_L(j)), fk_L(j), ek(j, "rail_top_L"), ek(j, "lat_v1"), env_L)
        loop_U = make_loop(lk(fk_U(j)), fk_U(j), ek(j, "rail_top_U"), ek(j, "lat_v0"), env_U)
        # CylSurf axis base sits at the START plane [V]
        axis = [_clean(c.center[0]), _clean(c.center[1]), _clean(zs)]
        make_face(fk_L(j), tj["side_L"], loop_L,
                  cylsurf(axis, c.radius, math.pi, TWO_PI, length))
        make_face(fk_U(j), tj["side_U"], loop_U,
                  cylsurf(axis, c.radius, s, s + math.pi, length))
        faces_out += [reg[fk_L(j)], reg[fk_U(j)]]

    # --- edges -----------------------------------------------------------------
    # per circle, in tag/pid order: rail_top_L, rail_bot_L, rail_top_U,
    # rail_bot_U, lat_v1, lat_v0  [V]
    edges_out: List[dict] = []
    # loop membership (cyclic) -- exactly the specimen's traversal [V]:
    #   top cap loop j    = [rail_top_L, rail_top_U]
    #   bottom cap loop j = [rail_bot_U, rail_bot_L]
    #   side L loop       = [rail_top_L, lat_v0, rail_bot_L, lat_v1]
    #   side U loop       = [rail_top_U, lat_v1, rail_bot_U, lat_v0]
    def loops_for(j: int) -> Dict[str, List[str]]:
        return {
            f"top{j}": [ek(j, "rail_top_L"), ek(j, "rail_top_U")],
            f"bot{j}": [ek(j, "rail_bot_U"), ek(j, "rail_bot_L")],
            fk_L(j): [ek(j, "rail_top_L"), ek(j, "lat_v0"), ek(j, "rail_bot_L"), ek(j, "lat_v1")],
            fk_U(j): [ek(j, "rail_top_U"), ek(j, "lat_v1"), ek(j, "rail_bot_U"), ek(j, "lat_v0")],
        }

    def loop_owner_key(loop_name: str, j: int) -> str:
        # the EdgeLoop object key that owns a named loop
        if loop_name == f"top{j}":
            return f"loop_{F_TOP}_{j}"
        if loop_name == f"bot{j}":
            return f"loop_{F_BOT}_{j}"
        return lk(loop_name)                    # side face's own loop

    def link(loop_name: str, j: int, edge_key: str) -> Tuple[dict, dict]:
        seq = loops_for(j)[loop_name]
        i = seq.index(edge_key)
        owner = loop_owner_key(loop_name, j)
        nxt = _sym(seq[i + 1]) if i + 1 < len(seq) else _sym(owner)
        prv = _sym(seq[i - 1]) if i > 0 else _sym(owner)
        return nxt, prv

    def uv_pair(p3, face_a, face_b, j, s):
        """[uv in face A, uv in face B] for a 3D point; faces are 'top',
        'bot', 'L', 'U' (of circle j; s = its U shift)."""
        def one(fc):
            th = math.atan2(p3[1] - C[j].center[1], p3[0] - C[j].center[0])
            if fc == "top":
                return uv_top(p3)
            if fc == "bot":
                return uv_bot(p3)
            if fc == "L":
                return _uv([theta_L(th), p3[2] - zs])
            return _uv([theta_U(th, s), p3[2] - zs])
        return [one(face_a), one(face_b)]

    def make_edge(j: int, role: str, tag: int, face_a: str, face_b: str,
                  loops_ab: Tuple[str, str], pts3: List[List[float]],
                  curved: bool, flags: int, ginfo_flags: int) -> None:
        s = shifts[j]
        key = ek(j, role)
        nxa, pva = link(loops_ab[0], j, key)
        nxb, pvb = link(loops_ab[1], j, key)
        e = blank_object("Edge")
        e["m_GInfo"] = ginfo(tag=tag, flags=ginfo_flags)
        e["m_pFace"] = [_sym({"top": F_TOP, "bot": F_BOT, "L": fk_L(j), "U": fk_U(j)}[face_a]),
                        _sym({"top": F_TOP, "bot": F_BOT, "L": fk_L(j), "U": fk_U(j)}[face_b])]
        e["m_next"] = [nxa, nxb]
        e["m_prev"] = [pva, pvb]
        e["m_interiorEdgePnts"] = ([{"uv": uv_pair(p, face_a, face_b, j, s)}
                                     for p in pts3[1:-1]] if curved else [])
        e["m_firstAndLastEdgePnts"] = [
            {"uv": uv_pair(pts3[0], face_a, face_b, j, s)},
            {"uv": uv_pair(pts3[-1], face_a, face_b, j, s)},
        ]
        e["m_flags"] = int(flags)
        edges_out.append(reg_ptr(key, "Edge", e))
        node_pts.extend(_v(p) for p in pts3)

    for j, c in enumerate(C):
        tj = tags[j]
        # arc node angles (world): the L half runs theta pi..2pi (7 chords),
        # the U half runs theta 0..pi (6 chords) [V]
        aL = [math.pi + i * (math.pi / ARC_CHORDS_FIRST_HALF)
              for i in range(ARC_CHORDS_FIRST_HALF + 1)]
        aU = [i * (math.pi / ARC_CHORDS_SECOND_HALF)
              for i in range(ARC_CHORDS_SECOND_HALF + 1)]
        top_L = [c.point(a, ze) for a in aL]                 # V0(top) -> V1(top)
        bot_L = [c.point(a, zs) for a in reversed(aL)]       # V1(bot) -> V0(bot)
        top_U = [c.point(a, ze) for a in aU]                 # V1(top) -> V0(top)
        bot_U = [c.point(a, zs) for a in reversed(aU)]       # V0(bot) -> V1(bot)
        # curved rails: forward in the CAP (face A), reversed in the side (B)
        make_edge(j, "rail_top_L", tj["rail_top_L"], "top", "L", (f"top{j}", fk_L(j)),
                  top_L, True, EDGE_FLAGS_CURVED_FORWARD_IN_A, EDGE_INFO_FLAGS)
        make_edge(j, "rail_bot_L", tj["rail_bot_L"], "bot", "L", (f"bot{j}", fk_L(j)),
                  bot_L, True, EDGE_FLAGS_CURVED_FORWARD_IN_A, EDGE_INFO_FLAGS)
        make_edge(j, "rail_top_U", tj["rail_top_U"], "top", "U", (f"top{j}", fk_U(j)),
                  top_U, True, EDGE_FLAGS_CURVED_FORWARD_IN_A, EDGE_INFO_FLAGS)
        make_edge(j, "rail_bot_U", tj["rail_bot_U"], "bot", "U", (f"bot{j}", fk_U(j)),
                  bot_U, True, EDGE_FLAGS_CURVED_FORWARD_IN_A, EDGE_INFO_FLAGS)
        # straight seams, stored top -> bottom, forward in face A [V]
        make_edge(j, "lat_v1", tj["lat_v1"], "U", "L", (fk_U(j), fk_L(j)),
                  [c.point(0.0, ze), c.point(0.0, zs)], False,
                  EDGE_FLAGS_FORWARD_IN_A, EDGE_SEAM_INFO_FLAGS)
        make_edge(j, "lat_v0", tj["lat_v0"], "L", "U", (fk_L(j), fk_U(j)),
                  [c.point(math.pi, ze), c.point(math.pi, zs)], False,
                  EDGE_FLAGS_FORWARD_IN_A, EDGE_SEAM_INFO_FLAGS)

    # --- Geometry + GElement root ----------------------------------------------
    geom = blank_object("Geometry")
    geom["m_GInfo"] = ginfo(category=geometry_style_id, tag=-1,
                            control_command=control_command, flags=GEOMETRY_FLAGS)
    geom["m_pFaces"] = faces_out
    geom["m_flags"] = GEOMETRY_FLAGS_CURVED
    geom["m_geometryTag"] = INVALID
    geom["m_tessEpsCntrl"] = {"m_type": 0, "m_TessEpsCntrlVersion": int(tess_version)}
    geom["m_pEdges"] = edges_out
    geom["m_sharedSurfInfo"] = []

    # the solid's bbox = the extents of its stored edge NODES (tessellated,
    # not the analytic circle) -- reproduces the specimen's -0.62187 exactly [V]
    bbox = [[min(p[i] for p in node_pts) for i in range(3)],
            [max(p[i] for p in node_pts) for i in range(3)]]
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(tag=element_id, flags=GELEM_ROOT_FLAGS)
    root["m_subNodes"] = [_ptr("Geometry", geom)]
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_elementId"] = int(element_id)
    root["m_gElemType"] = 3
    root["m_flags"] = 0
    _number_graph(root, reg)
    _assert_pid_stable(root)
    return root


def new_arc_curve_elem(elem_id: int, ctx: FamilyDocContext, *, sketch_plane_id: int,
                       sketch_id: int, extrusion_id: int, center: Vec, radius: float,
                       ang0: float, ang1: float, partner_id: int, tag: int = 0,
                       notes=None) -> SkelElement:
    """One half-arc of a circle profile as a model ``CurveElem`` (category
    OST_Lines): driver ``GArc``, the arc-centre marker ``m_oArcCntr``, an
    ``ArcElemCell``, two curve-history entries, and endpoint joins to its
    partner half (this end 0 = partner's end 1, this end 1 = partner's
    end 0) [V rfa 3736/3741]."""
    obj = _base("CurveElem", elem_id, family_id=ctx.family_id,
                int_params={BIP_CURVE_ELEM_INT: 1})
    st = blank_object("CurveElemGStep")
    st["m_faceHistTable"] = []
    st["m_curveHistTableSet"] = [{"m_id": 0, "m_curveHist": {"m_keys": [2, 0, -1, -1, -1]}},
                                 {"m_id": 1, "m_curveHist": {"m_keys": [2, 1, -1, -1, -1]}}]
    st["m_edgeHistTable"] = []
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = 1
    st["m_version"] = 0
    st["m_flags"] = 0
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    obj["m_geomSteps"] = _gstep_list([], [_ptr("CurveElemGStep", st)],
                                     latest=1, id_counter=2, flags=1)
    obj["m_pGeomTable"] = _geom_table(2)
    obj["m_cellList"] = _cell_list(
        _owned("SketchMembership", m_groupId=int(sketch_id)),
        _owned("ArcElemCell"), _pattern_helper())
    drv = blank_object("CurveElemDriver")
    drv["m_oControlData"] = None
    drv["m_pCrv"] = garc(center, radius, ang0, ang1, tag=int(tag), flags=ctx.gline_flags)
    drv["m_sideJoins"] = []
    drv["m_controlJoinsSet"] = [
        _join_entry(0, [(elem_id, 0), (partner_id, 1)]),
        _join_entry(1, [(elem_id, 1), (partner_id, 0)]),
    ]
    drv["m_midParams"] = []
    drv["m_nextMidParamId"] = 4
    drv["m_flip"] = False
    drv["m_sideAlignments"] = []
    obj["m_pCurveDriver"] = _ptr("CurveElemDriver", drv)
    obj["m_data"] = {"m_oUserData": None, "m_oAssocProp": None}
    obj["m_oArcCntr"] = arc_center_marker(center, flags=ctx.gline_flags)
    obj["m_oEllipseElemData"] = None
    obj["m_categoryId"] = INVALID
    obj["m_sketchPlaneId"] = int(sketch_plane_id)
    obj["m_areaSchemeId"] = INVALID
    obj["m_zoneSchemeId"] = INVALID
    obj["m_famElemVisibility"] = {"m_flags": -1}
    obj["m_referenceType"] = 1              # rfa arc CurveElem specimen value [V]
    obj["m_areaSeparation"] = False
    obj["m_bMEPSpaceSeparation"] = False
    obj["m_bMEPLoadAreaSeparation"] = False
    obj["m_isAreaMeasurementScheme"] = False
    obj["m_detail"] = False
    obj["m_showCenterMark"] = False
    obj["m_useOffsetPos"] = False
    assign_pids(obj)
    # rep: the arc as a one-node GElement (root flags 32, curved rep flags)
    a0, a1 = float(ang0), float(ang1)
    bbox = _arc_bbox(center, radius, a0, a1)
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(category=ctx.curve_style_id, tag=elem_id,
                             flags=GELEM_CURVE_ROOT_FLAGS)
    root["m_subNodes"] = [garc(center, radius, a0, a1, tag=int(tag),
                                flags=ctx.gline_flags + GLINE_REP_CURVE_DELTA)]
    root["m_bBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_tightbBox"] = [_cv(bbox[0]), _cv(bbox[1])]
    root["m_elementId"] = int(elem_id)
    root["m_gElemType"] = 2
    root["m_flags"] = 32
    assign_pids(root)
    hdr = _hdr("CurveElem", ctx, elem_id, category=BIC_LINES,
               deletion=[ctx.family_id, sketch_plane_id, sketch_id, partner_id],
               appearance=[sketch_id], regen_only=[ctx.level_id, extrusion_id],
               nondeterm=True, misc_id=sketch_id, bbox=None)  # donor law #52: headers carry no bbox
    return SkelElement(elem_id, "CurveElem", hdr, obj, root, kind="curve",
                       owner_id=sketch_id,
                       refs={"sketch": sketch_id, "sketch_plane": sketch_plane_id,
                             "partner": partner_id},
                       notes=list(notes or []))


def _arc_bbox(center: Vec, radius: float, ang0: float, ang1: float) -> List[List[float]]:
    """Analytic axis-aligned bbox of an arc (feet, in the sketch plane)."""
    r = float(radius)
    cands = [float(ang0), float(ang1)]
    for k in range(-4, 9):                                  # cardinal angles
        a = k * math.pi / 2.0
        if ang0 - 1e-12 <= a <= ang1 + 1e-12:
            cands.append(a)
    xs = [float(center[0]) + r * math.cos(a) for a in cands]
    ys = [float(center[1]) + r * math.sin(a) for a in cands]
    return [[_clean(min(xs)), _clean(min(ys)), 0.0],
            [_clean(max(xs)), _clean(max(ys)), 0.0]]



#: The parameter vector a curve's solver record declares.  A LINE's four are
#: its endpoint coordinates (x1, y1, x2, y2) -- the donor law #333 established.
#: An ARC's degrees of freedom are its centre, radius and the two end angles;
#: the schema's own ``VarSketchArcEndAngleConstrObj(m_angle, m_end)`` exists to
#: pin an end angle, which only makes sense if the angles are parameters.
#: Overridable so a desktop round can decide the layout empirically (#589).
ARC_SOLVER_PARAMS = "center_radius_angles"


def _curve_solver_params(curve: dict) -> List[float]:
    """The numeric parameters of one absorbed curve token."""
    v = (curve or {}).get("value") or {}
    cls = (curve or {}).get("ptr_class")
    if cls == "GArc":
        cx, cy = float(v["m_center"][0]), float(v["m_center"][1])
        r = float(v["m_radius"])
        a0, a1 = (float(x) for x in v["m_endParams"])
        if ARC_SOLVER_PARAMS == "center_radius":
            return [cx, cy, r]
        return [cx, cy, r, a0, a1]
    if cls == "GLine":                      # origin + dirVec * endParams
        ox, oy = float(v["m_origin"][0]), float(v["m_origin"][1])
        dx, dy = float(v["m_dirVec"][0]), float(v["m_dirVec"][1])
        t0, t1 = (float(x) for x in v["m_endParams"])
        return [ox + dx * t0, oy + dy * t0, ox + dx * t1, oy + dy * t1]
    return []


def _curve_solver_obj(curve: dict, curve_id: int) -> dict:
    """One ``m_elemRecs`` entry for an absorbed curve: the solver object
    ``VarSketch::getCurveObj`` resolves that curve to (issue #589)."""
    cls = (curve or {}).get("ptr_class")
    body = {
        "m_params": [_ptr("VarParam", {"m_refCt": 1, "m_val": float(c)})
                     for c in _curve_solver_params(curve)],
        "m_pSketch": _weak(2),
        "m_objId": int(curve_id),
        "m_angleCoef": 1.0,
        "m_unbounded": False,
    }
    if cls == "GArc":
        body["m_flipped"] = False
        return _ptr("VarSketchArcObj", body)
    return _ptr("VarSketchLineSegObj", body)


def new_var_sketch_curves(elem_id: int, ctx: FamilyDocContext, *,
                          sketch_plane_id: int, user_id: int,
                          curves: Sequence[dict], curve_ids: Sequence[int],
                          bbox: Optional[Sequence[Sequence[float]]] = None,
                          dim_ids: Sequence[int] = (), notes=None) -> SkelElement:
    """A ``VarSketch`` from arbitrary curve tokens (GLine / GArc), given
    already tagged 0..n-1 with the standalone-flavour flags -- the general
    form of :func:`new_var_sketch` (which draws straight lines)."""
    n = len(curves)
    if n != len(curve_ids):
        raise ValueError("one CurveElem id per sketch curve")
    obj = _base("VarSketch", elem_id, family_id=ctx.family_id)
    st = blank_object("RegenSketchCurvesGStep")
    st["m_faceHistTable"] = []
    st["m_curveHistTableSet"] = [{"m_id": i, "m_curveHist": {"m_keys": [1, i, -1, -1, -1]}}
                                 for i in range(n)]
    st["m_edgeHistTable"] = []
    st["m_edgeHistTableReverse"] = []
    st["m_id"] = 1
    st["m_version"] = 0
    st["m_flags"] = 0
    st["m_pElem"] = _weak(2)
    st["m_oExtraDatas"] = None
    obj["m_geomSteps"] = _gstep_list([], [_ptr("RegenSketchCurvesGStep", st)],
                                     latest=1, id_counter=2, flags=1)
    obj["m_pGeomTable"] = _geom_table(n)
    grp = _owned("SketchGroupHelper",
                 m_pElemIdsPairSet=_owned("ElementIdIndexPairSet", m_data=[]),
                 m_nextIndex=0)
    obj["m_cellList"] = _cell_list(grp, _pattern_helper())
    obj["m_elemIdsPairSet"] = _owned("ElementIdIndexPairSet",
                                    m_data=[{"m_elementId": int(cid), "m_index": i}
                                            for i, cid in enumerate(curve_ids)])
    obj["m_pPointIdsPairSet"] = _owned("ElementIdIndexPairSet", m_data=[])
    obj["m_dimIds"] = [int(d) for d in dim_ids]
    obj["m_clineIds"] = []
    env2 = ([[bbox[0][0], bbox[0][1]], [bbox[1][0], bbox[1][1]]] if bbox is not None
            else [[0.0, 0.0], [0.0, 0.0]])
    obj["m_pPlane"] = plane([0, 0, 0], [1, 0, 0], [0, 1, 0], env2)
    obj["m_oSketchGridData"] = None
    obj["m_refPnt"] = None
    obj["m_sketchPlaneId"] = int(sketch_plane_id)
    obj["m_serFlags"] = 1
    obj["m_nextIndex"] = n
    obj["m_isEdited"] = 0
    obj["m_version"] = 0
    obj["m_remainVisible"] = False
    obj["m_isSuspendedNew"] = False
    obj["m_allowResetLineEndConstr"] = True
    obj["m_isHostForReferenceLines"] = False
    obj["m_flipXY"] = False
    obj["m_flipZ"] = False
    obj["m_absorbedCurves"] = [copy.deepcopy(c) for c in curves]
    obj["m_absorbedCurvesData"] = [
        _owned("CurveElemData", m_oUserData=None, m_oAssocProp=None) for _ in range(n)]
    obj["m_customDatumPlanes"] = []
    obj["m_pPlaneRef"] = None
    # SOLVER STATE for CURVE sketches (issue #589).  Leaving m_elemRecs empty
    # while m_curveObjIdxMap names every curve is the very shape issue #333
    # falsified for line sketches: VarSketch::getCurveObj indexes m_elemRecs
    # THROUGH that map, so an empty array with a 2-entry map is an
    # out-of-range read.  Revit 2026 survives OPENING such a family and dies
    # inside Insert > Load Family -- "Invalid idx in VarSketch::getCurveObj
    # (VarSketch.cpp:634)" + 0xc0000005 (owner journal 0040, 2026-08-10).
    # One solver record per curve, of the class the file's own schema gives
    # for that curve kind (GArc -> VarSketchArcObj, which extends
    # VarSketchCurveObj -> VarSketchObj and adds m_flipped).
    obj["m_elemRecs"] = [_curve_solver_obj(c, int(cid))
                         for c, cid in zip(curves, curve_ids)]
    obj["m_curveObjIdxMap"] = [{"first": int(cid), "second": i}
                               for i, cid in enumerate(curve_ids)]
    obj["m_pointRecs"] = []
    obj["m_pointObjIdxMap"] = []
    obj["m_constrRecs"] = []
    gc = blank_object("VarSketchGuessCache")
    gc["m_pSketch"] = _weak(2)
    gc["m_guessArr"] = [_ptr("VarSketchGuess", {
        "m_values": [v for c in curves for v in _curve_solver_params(c)],
        "m_useCount": 29})] if curves else []
    gc["m_nPar"] = 0
    obj["m_oGuessCache"] = _ptr("VarSketchGuessCache", gc)
    obj["m_oParamPlane"] = plane([0, 0, 0], [1, 0, 0], [0, 1, 0],
                                  [[1.0, 1.0], [0.0, 0.0]])
    obj["m_dimData"] = []
    obj["m_weakDimIds"] = []
    obj["m_autodimDisabled"] = False
    obj["m_isParametric"] = True
    obj["m_highResidualTol"] = False
    obj["m_userId"] = int(user_id)
    assign_pids(obj)
    # rep: the sketch curves as a GElement of curve nodes (gElemType 2,
    # root flags 0, rep copies carry the +0x8000 flag and tag -1) [V 613]
    root = blank_object("GElement")
    root["m_GInfo"] = ginfo(tag=elem_id, flags=GELEM_ROOT_FLAGS)
    rep_nodes = []
    for c in curves:
        cc = copy.deepcopy(c)
        cc["value"]["m_GInfo"]["m_tag"] = -1
        cc["value"]["m_GInfo"]["m_flags"] = ctx.gline_flags + GLINE_REP_SKETCH_DELTA
        rep_nodes.append(cc)
    root["m_subNodes"] = rep_nodes
    bb = bbox if bbox is not None else [[0, 0, 0], [0, 0, 0]]
    root["m_bBox"] = [_cv(bb[0]), _cv(bb[1])]
    root["m_tightbBox"] = [_cv(bb[0]), _cv(bb[1])]
    root["m_elementId"] = int(elem_id)
    root["m_gElemType"] = 2
    root["m_flags"] = 0
    assign_pids(root)
    hdr = _hdr("VarSketch", ctx, elem_id,
               deletion=[ctx.family_id, sketch_plane_id, user_id, *curve_ids, *dim_ids],
               regen_only=[ctx.level_id], bbox=None)  # donor law #52
    return SkelElement(elem_id, "VarSketch", hdr, obj, root, kind="sketch",
                       owner_id=user_id,
                       refs={"sketch_plane": sketch_plane_id, "extrusion": user_id,
                             "curves": list(curve_ids)},
                       notes=list(notes or []))


def new_cylinder_extrusion(elem_id: int, ctx: FamilyDocContext, *, sketch_id: int,
                           sketch_plane_id: int, circles: Sequence[CircleProfile],
                           start: float, end: float, rep: str = REP_SOLID,
                           category_id: int = INVALID, material_id: int = INVALID,
                           notes=None,
                   always_ref_plane_norm: bool = False) -> SkelElement:
    """The ``ExtrusionElem`` of a circle-profile form: start/end offsets
    (extrude-UP), the two-arc-loop ExtrusionGStep tag map, the per-tag
    geometry table, the private helper copy of each circle loop (traversal
    L then U -- arcs keep the sketch's parametrization, params [-pi,0]
    then [0,pi]) [V 614], and the rep: our authored CylSurf B-rep
    (``rep='solid'``) or ``SerializedDummy``."""
    C = list(circles)
    k = len(C)
    if not float(end) > float(start):
        raise ValueError("cylinder extrusions are extrude-UP: end > start")
    obj = _base("ExtrusionElem", elem_id, family_id=ctx.family_id,
                int_params={BIP_CURVE_ELEM_INT: 1},
                double_params_ordered=[
                    # Revit reads -1001800 as "Extrusion Start" and -1001801
                    # as "Extrusion End", and shows Depth = End - Start.  The
                    # box path traces extrude-DOWN (its `start` IS the top),
                    # so writing the raw pair put the top in Start and gave
                    # every box a NEGATIVE depth in the properties palette
                    # [owner screenshot: Start 0'5 3/4", End 0'0",
                    # Depth -0'5 3/4"].  Order by elevation, not by the
                    # tracer's direction; the B-rep is unaffected.
                    (BIP_EXTRUSION_END, max(float(start), float(end))),
                    (BIP_EXTRUSION_START, min(float(start), float(end)))])
    step = extrusion_gstep_circles(k)
    obj["m_geomSteps"] = _gstep_list([_ptr("ExtrusionGStep", step)],
                                     latest=2, id_counter=2, flags=9)
    obj["m_pGeomTable"] = _geom_table(2 + 8 * k)
    loops = []
    for j, c in enumerate(C):
        cl = blank_object("CurveLoop")
        cl["m_open"] = False
        # traversal L (drawn index 2j+1) then U (2j), tags = the sketch's
        cl["m_curves"] = [
            garc(c.center, c.radius, *CircleProfile.ANG_L, tag=2 * j + 1,
                 flags=ctx.gline_flags),
            garc(c.center, c.radius, *CircleProfile.ANG_U, tag=2 * j,
                 flags=ctx.gline_flags),
        ]
        loops.append(_ptr("CurveLoop", cl))
    helper = _owned("ExtrusionElemExtrusionHelper", m_sketchId=int(sketch_id),
                    m_complete=True, m_pCurveLoops=loops)
    obj["m_cellList"] = _cell_list(
        helper, _owned("GenSweepPatternHelper", m_PatternPositionMap=[],
                       m_substituteFaceMap=[]))
    obj["m_categoryId"] = int(category_id)
    obj["m_materialId"] = int(material_id)
    obj["m_famElemVisibility"] = {"m_flags": int(ctx.fam_elem_visibility)}
    obj["m_cutting"] = False
    obj["m_alwaysRefPlaneNorm"] = bool(always_ref_plane_norm)
    obj["m_sideRefPlaneCurveBased"] = False
    assign_pids(obj)
    if rep == REP_SOLID:
        solid = solid_cylinder_brep(C, start, end, element_id=elem_id,
                                    geometry_style_id=ctx.geometry_style_id,
                                    control_command=ctx.solid_control_command,
                                    tess_version=ctx.tess_version)
    elif rep == REP_DUMMY:
        solid = None
    else:
        raise ValueError(f"rep must be {REP_SOLID!r} or {REP_DUMMY!r}")
    rmax = max(c.radius for c in C)
    xs = [c.center[0] for c in C]
    ys = [c.center[1] for c in C]
    hdr_bbox = [[min(xs) - rmax, min(ys) - rmax, float(start)],
                [max(xs) + rmax, max(ys) + rmax, float(end)]]
    hdr = _hdr("ExtrusionElem", ctx, elem_id,
               deletion=[ctx.family_id, sketch_id],
               appearance=[ctx.family_id, sketch_id],
               regen_only=[*ctx.extra_regen_ids, sketch_plane_id], bbox=hdr_bbox)
    return SkelElement(elem_id, "ExtrusionElem", hdr, obj, solid, kind="extrusion",
                       owner_id=ctx.family_id,
                       refs={"sketch": sketch_id, "sketch_plane": sketch_plane_id,
                             "params": {"start_ft": float(start), "end_ft": float(end)}},
                       notes=list(notes or []))


def cylinder_form(circle: CircleProfile, height_ft: float, ctx: FamilyDocContext,
                  ids: Any, *, base_z_ft: float = 0.0, rep: str = REP_SOLID,
                  kind: str = "cylinder", material_id: int = INVALID,
                  category_id: int = INVALID) -> FormBundle:
    """The complete element cluster of a cylindrical form: SketchPlane +
    VarSketch (two half arcs) + 2 arc ``CurveElem`` + ``ExtrusionElem``,
    from z = base_z (start) UP to z = base_z + height (end)."""
    if height_ft <= 0:
        raise ValueError("height must be positive")
    id_plane = _alloc(ids)
    id_sketch = _alloc(ids)
    id_u = _alloc(ids)                     # upper half arc, params [0, pi] (drawn 1st)
    id_l = _alloc(ids)                     # lower half arc, params [-pi, 0]
    id_ext = _alloc(ids)
    start = float(base_z_ft)
    end = float(base_z_ft) + float(height_ft)
    c = circle
    arc_u = garc(c.center, c.radius, *CircleProfile.ANG_U, tag=0, flags=ctx.gline_flags)
    arc_l = garc(c.center, c.radius, *CircleProfile.ANG_L, tag=1, flags=ctx.gline_flags)
    sk_bbox = [[c.center[0] - c.radius, c.center[1] - c.radius, 0.0],
               [c.center[0] + c.radius, c.center[1] + c.radius, 0.0]]
    elems: List[SkelElement] = []
    elems.append(new_sketch_plane(id_plane, ctx, sketch_id=id_sketch))
    elems.append(new_var_sketch_curves(id_sketch, ctx, sketch_plane_id=id_plane,
                                       user_id=id_ext, curves=[arc_u, arc_l],
                                       curve_ids=[id_u, id_l], bbox=sk_bbox))
    elems.append(new_arc_curve_elem(id_u, ctx, sketch_plane_id=id_plane, sketch_id=id_sketch,
                                    extrusion_id=id_ext, center=c.center, radius=c.radius,
                                    ang0=CircleProfile.ANG_U[0], ang1=CircleProfile.ANG_U[1],
                                    partner_id=id_l, tag=0))
    elems.append(new_arc_curve_elem(id_l, ctx, sketch_plane_id=id_plane, sketch_id=id_sketch,
                                    extrusion_id=id_ext, center=c.center, radius=c.radius,
                                    ang0=CircleProfile.ANG_L[0], ang1=CircleProfile.ANG_L[1],
                                    partner_id=id_u, tag=0))
    elems.append(new_cylinder_extrusion(id_ext, ctx, sketch_id=id_sketch,
                                        sketch_plane_id=id_plane, circles=[c],
                                        start=start, end=end, rep=rep,
                                        material_id=material_id, category_id=category_id))
    params = {"radius_ft": c.radius, "height_ft": float(height_ft),
              "base_z_ft": float(base_z_ft), "start_ft": start, "end_ft": end,
              "center": [c.center[0], c.center[1]], "rep": rep}
    notes = [
        "profile: two half-arc CurveElems (upper [0,pi] drawn first, lower "
        "[-pi,0]) about one centre, in a VarSketch on the Ref. Level SketchPlane",
        "ExtrusionElem params -1001800 start (bottom) / -1001801 end (top): "
        "extrude-UP, the frame every corpus cylinder uses",
        ("rep=solid: cached CylSurf B-rep authored by solid_cylinder_brep "
         "(2 planar caps + 2 half-cylinder faces, 4 curved rails with the "
         "specimen's 7/6-chord tessellation, 2 straight seams)"
         if rep == REP_SOLID else
         "rep=dummy: SerializedDummy -- Revit must regenerate the solid on load (F4b)"),
        "solver state (VarSketch.m_elemRecs/m_constrRecs/guess cache) left EMPTY [H]",
    ]
    return FormBundle(kind, elems, params, notes)


def cylinder(radius_ft: float, height_ft: float, ctx: FamilyDocContext, ids: Any,
             *, base_z_ft: float = 0.0, center: Vec = (0.0, 0.0),
             rep: str = REP_SOLID) -> FormBundle:
    """A CYLINDER form (a recessed can / a leg): radius x height, centred at
    ``center`` in plan, from z = base_z up to z = base_z + height, drawn as
    Revit sketches a circle -- two half arcs -- and extruded UP.

    E.g. a 6 in. recessed can: ``cylinder(inches(3), inches(7.5), ctx, ids)``.
    """
    return cylinder_form(circle_profile(center, radius_ft), height_ft, ctx, ids,
                         base_z_ft=base_z_ft, rep=rep)


# ---------------------------------------------------------------------------
# specimen extraction (the topology-reproduction proof feeds these back in)
# ---------------------------------------------------------------------------

def specimen_box_inputs(doc, unit: int, extrusion_id: int) -> dict:
    """Read a SPECIMEN box extrusion's DIMENSIONS (nothing else): its
    traced profile vertices (from the ExtrusionElemExtrusionHelper loop),
    its start/end offsets, and the graphics context ints.  The topology
    proof rebuilds the solid from JUST these and compares against the
    specimen's decoded seq-103 GElement.
    """
    from ..families import _index
    idx = _index(doc)
    v = idx.value(unit, extrusion_id)
    if v is None:
        raise ValueError(f"no element {extrusion_id} in unit {unit}")
    params = {p["m_paramId"]: p["m_value"]
              for p in ((v.get("m_pParamValueSetDouble") or {}).get("value") or {}
                        ).get("m_paramSet") or []}
    cells = (v.get("m_cellList") or {}).get("value", {}).get("m_cells") or []
    helper = next((c for c in cells if c.get("ptr_class") == "ExtrusionElemExtrusionHelper"), None)
    if helper is None:
        raise ValueError("no ExtrusionElemExtrusionHelper cell")
    curves = helper["value"]["m_pCurveLoops"][0]["value"]["m_curves"]
    verts = []
    for c in curves:
        if c["ptr_class"] != "GLine":
            raise ValueError("profile is not a straight-line loop")
        cv = c["value"]
        o, d = _v(cv["m_origin"]), _v(cv["m_dirVec"])
        t0 = float(cv["m_endParams"][0])
        # curve start point = origin + t0*dir (traced-loop curves end at t=0)
        verts.append(_cv(_add(o, _mul(d, t0))))
    rep = idx.decode(unit, extrusion_id, 103)
    geo = ((rep.value.get("m_subNodes") or [{}])[0].get("value") or {}) if rep else {}
    gi = geo.get("m_GInfo") or {}
    return {"element_id": int(extrusion_id),
            "vertices": [[x, y] for x, y, _z in verts],
            "start": float(params[BIP_EXTRUSION_START]),
            "end": float(params[BIP_EXTRUSION_END]),
            "sketch_z": float(verts[0][2]),
            "geometry_style_id": int(gi.get("m_categoryId", -1)),
            "control_command": int(gi.get("m_controlCommand", 0)),
            "specimen_rep": rep.value if rep else None}


def compare_object_trees(a: Any, b: Any, *, path: str = "$", ftol: float = 1e-9,
                         out: Optional[dict] = None) -> dict:
    """Leaf-by-leaf comparison of two decoded object trees.

    Returns {'structural_mismatches': [...], 'max_float_dev': f,
    'float_devs_over_tol': [...], 'n_leaves': k}: every non-float leaf
    (class names, pids, weakrefs, ints, flags, list lengths, keys) must be
    EQUAL; floats are compared with tolerance ``ftol``.
    """
    if out is None:
        out = {"structural_mismatches": [], "max_float_dev": 0.0,
               "float_devs_over_tol": [], "n_leaves": 0}
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            out["structural_mismatches"].append(f"{path}: keys {sorted(set(a) ^ set(b))}")
        for k in a:
            if k in b:
                compare_object_trees(a[k], b[k], path=f"{path}.{k}", ftol=ftol, out=out)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out["structural_mismatches"].append(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            compare_object_trees(x, y, path=f"{path}[{i}]", ftol=ftol, out=out)
        return out
    out["n_leaves"] += 1
    if isinstance(a, bool) or isinstance(b, bool):
        if bool(a) != bool(b):
            out["structural_mismatches"].append(f"{path}: {a!r} != {b!r}")
        return out
    if isinstance(a, float) or isinstance(b, float):
        try:
            dev = abs(float(a) - float(b))
        except (TypeError, ValueError):
            out["structural_mismatches"].append(f"{path}: {a!r} != {b!r}")
            return out
        out["max_float_dev"] = max(out["max_float_dev"], dev)
        if dev > ftol:
            out["float_devs_over_tol"].append(f"{path}: {a} vs {b} (dev {dev:.3g})")
        return out
    if a != b:
        out["structural_mismatches"].append(f"{path}: {a!r} != {b!r}")
    return out


def _canonical(v: Any, digits: int, *, in_ginfo: bool = False) -> Any:
    """Canonical form for byte comparison: floats snapped to ``digits``
    decimals (specimens carry ~1e-15 transform noise) and the volatile
    GInfo bit 0x200 cleared (it differs between the two Autodesk box
    specimens of the same family -- see GINFO_VOLATILE_BIT)."""
    if isinstance(v, float):
        r = round(v, digits)
        return 0.0 if r == 0 else r          # -0.0 -> 0.0
    if isinstance(v, dict):
        gi = ("m_categoryId" in v and "m_tag" in v and "m_controlCommand" in v
              and "m_flags" in v)
        out = {}
        for k, x in v.items():
            if gi and k == "m_flags" and isinstance(x, int):
                out[k] = x & ~GINFO_VOLATILE_BIT
            else:
                out[k] = _canonical(x, digits)
        return out
    if isinstance(v, list):
        return [_canonical(x, digits) for x in v]
    return v


def _volatile_only(structural_mismatches: List[str]) -> bool:
    """True when every structural mismatch is the GInfo bit 0x200."""
    for m in structural_mismatches:
        if not m.rsplit(".", 1)[-1].startswith("m_flags: "):
            return False
        try:
            _lbl, vals = m.rsplit(".m_flags: ", 1)
            a, b = (int(x) for x in vals.split(" != "))
        except ValueError:
            return False
        if (a ^ b) != GINFO_VOLATILE_BIT:
            return False
    return True


def reproduce_specimen_solid(doc, unit: int, extrusion_id: int, *,
                             digits: int = 9) -> dict:
    """THE TOPOLOGY PROOF: rebuild a specimen box solid from its six
    dimensions and compare with the specimen's own decoded GElement.

    Reports (a) structural exactness -- every class/pid/weakref/int/key
    identical; (b) the max float deviation; (c) CANONICAL BYTE-EXACTNESS:
    both trees re-encoded after snapping floats to ``digits`` decimals
    produce identical bytes (the specimen carries ~1e-15 float noise from
    Revit's transform arithmetic that a clean generator does not).
    """
    from ..encode import ObjectEncoder
    from ..families import _index
    idx = _index(doc)
    sp = specimen_box_inputs(idx, unit, extrusion_id)
    z0 = sp["sketch_z"]
    ours = solid_box_brep(sp["vertices"], sp["start"] + z0, sp["end"] + z0,
                          element_id=sp["element_id"],
                          geometry_style_id=sp["geometry_style_id"],
                          control_command=sp["control_command"])
    theirs = sp["specimen_rep"]
    cmp = compare_object_trees(ours, theirs)
    enc = ObjectEncoder(idx.schema)
    cid = _class_id("GElement")
    b_ours = enc.encode_object(cid, _canonical(copy.deepcopy(ours), digits))
    b_theirs = enc.encode_object(cid, _canonical(copy.deepcopy(theirs), digits))
    b_exact_ours = enc.encode_object(cid, ours)
    b_exact_theirs = enc.encode_object(cid, theirs)
    only_volatile = _volatile_only(cmp["structural_mismatches"])
    return {
        "extrusion_id": extrusion_id,
        "inputs": {k: sp[k] for k in ("vertices", "start", "end", "sketch_z",
                                      "geometry_style_id", "control_command")},
        "structural_mismatches": cmp["structural_mismatches"],
        "structurally_exact": not cmp["structural_mismatches"],
        # exact except (at most) the documented volatile GInfo bit 0x200
        "structurally_exact_modulo_volatile_bit": (not cmp["structural_mismatches"]) or only_volatile,
        "n_leaves": cmp["n_leaves"],
        "max_float_dev": cmp["max_float_dev"],
        "float_devs_over_tol": cmp["float_devs_over_tol"][:10],
        "canonical_bytes_ours": len(b_ours),
        "canonical_bytes_specimen": len(b_theirs),
        "canonical_byte_exact": b_ours == b_theirs,
        "raw_byte_exact": b_exact_ours == b_exact_theirs,
        "raw_len_ours": len(b_exact_ours), "raw_len_specimen": len(b_exact_theirs),
        "digits": digits,
    }


# ---------------------------------------------------------------------------
# cylinder specimen (sample .rfa extrusion 614) -- extraction + reproduction
# ---------------------------------------------------------------------------

def _iter_owned_ptrs(value: Any) -> List[dict]:
    """The REGISTERED owned-pointer tokens of an object tree in exactly the
    archive numbering order :func:`assign_pids` uses (breadth-first)."""
    out: List[dict] = []
    q: deque = deque()

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            if "ptr_class" in v:
                if v["ptr_class"] in REGISTERED_CLASSES:
                    out.append(v)
                q.append(v.get("value"))
            elif "weakref" in v or "backref_pid" in v or "classref" in v:
                return
            else:
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
    return out


def renumber_pids(value: dict, start: int = 3) -> Dict[int, int]:
    """Renumber the archive object indices of ``value`` IN PLACE
    (:func:`assign_pids`) and remap every ``weakref`` that pointed at an
    old index -- so a graph can be edited (objects removed) and then
    canonically renumbered without dangling coedge/loop links.  Returns
    the old->new pid map."""
    ptrs = _iter_owned_ptrs(value)
    mapping = {int(p.get("pid", -1)): start + i for i, p in enumerate(ptrs)
               if int(p.get("pid", -1)) > 0}
    assign_pids(value, start)

    def remap(v: Any) -> None:
        if isinstance(v, dict):
            if "weakref" in v and isinstance(v.get("weakref"), int) and len(v) == 1:
                v["weakref"] = mapping.get(int(v["weakref"]), int(v["weakref"]))
                return
            for x in v.values():
                remap(x)
        elif isinstance(v, list):
            for x in v:
                remap(x)

    remap(value)
    return mapping


def _strip_fillings(gelement: dict) -> dict:
    """A deep copy of a solid GElement with every face's material surface
    FILLING removed (``m_pGFilling`` -> None) and its render style reset --
    the GFilling placer floats are cached pattern-layout state that is not
    derivable from geometry (docs sec. 4.4); our authored solids (like both
    accepted box specimens) carry none -- then canonically renumbered."""
    g = copy.deepcopy(gelement)
    for geo in g.get("m_subNodes") or []:
        for f in (geo.get("value") or {}).get("m_pFaces") or []:
            fv = f.get("value") or {}
            if fv.get("m_pGFilling") is not None:
                fv["m_pGFilling"] = None
            fv["m_renderStyleId"] = INVALID
    renumber_pids(g)
    return g


def specimen_cylinder_inputs(doc, unit: int, extrusion_id: int) -> dict:
    """Read a SPECIMEN circle-profile extrusion's DIMENSIONS + numbering
    facts (nothing structural): the circles (centre, radius) from its
    helper CurveLoops, start/end, the per-loop history TAG BASE (from its
    own ExtrusionGStep), the per-circle U-face theta shift and graphics ids
    (from its rep).  The reproduction rebuilds the whole solid from these.
    """
    from ..families import _index
    idx = _index(doc)
    v = idx.value(unit, extrusion_id)
    if v is None:
        raise ValueError(f"no element {extrusion_id} in unit {unit}")
    params = {p["m_paramId"]: p["m_value"]
              for p in ((v.get("m_pParamValueSetDouble") or {}).get("value") or {}
                        ).get("m_paramSet") or []}
    cells = (v.get("m_cellList") or {}).get("value", {}).get("m_cells") or []
    helper = next((c for c in cells if c.get("ptr_class") == "ExtrusionElemExtrusionHelper"), None)
    if helper is None:
        raise ValueError("no ExtrusionElemExtrusionHelper cell")
    step = v["m_geomSteps"]["value"]["m_bRepFormGList"][0]["value"]
    fkey = {tuple(x["m_faceHist"]["m_keys"]): int(x["m_id"]) for x in step["m_faceHistTable"]}
    circles: List[dict] = []
    tag_bases: List[int] = []
    for loop in helper["value"]["m_pCurveLoops"]:
        curves = loop["value"]["m_curves"]
        if len(curves) != 2 or any(c["ptr_class"] != "GArc" for c in curves):
            raise ValueError("loop is not a two-half-arc circle")
        cl_tag = int(curves[0]["value"]["m_GInfo"]["m_tag"])   # traversal curve 0 = L
        cv = curves[0]["value"]
        circles.append({"center": [float(cv["m_center"][0]), float(cv["m_center"][1])],
                        "radius": float(cv["m_radius"])})
        tag_bases.append(fkey[(3, cl_tag, -1)])              # side_L face tag = base
    rep = idx.decode(unit, extrusion_id, 103)
    geo = ((rep.value.get("m_subNodes") or [{}])[0].get("value") or {}) if rep else {}
    gi = geo.get("m_GInfo") or {}
    faces = geo.get("m_pFaces") or []
    ftag = {int(f["value"]["m_GInfo"]["m_tag"]): f for f in faces}
    u_shifts = []
    for base in tag_bases:
        fu = ftag[_circle_loop_tags(base)["side_U"]]
        u_shifts.append(float(fu["value"]["m_pSurf"]["value"]["m_Envelope"]["m_corners"][0][0]))
    render = int(faces[0]["value"].get("m_renderStyleId", INVALID)) if faces else INVALID
    tess = int((geo.get("m_tessEpsCntrl") or {}).get("m_TessEpsCntrlVersion", 0))
    return {"element_id": int(extrusion_id), "circles": circles,
            "start": float(params[BIP_EXTRUSION_START]),
            "end": float(params[BIP_EXTRUSION_END]),
            "tag_bases": tag_bases, "u_shifts": u_shifts,
            "geometry_style_id": int(gi.get("m_categoryId", -1)),
            "control_command": int(gi.get("m_controlCommand", 0)),
            "render_style_id": render, "tess_version": tess,
            "specimen_rep": rep.value if rep else None}


def reproduce_specimen_cylinders(doc, unit: int, extrusion_id: int, *,
                                 env_tol: float = 5e-4) -> dict:
    """THE CYLINDER TOPOLOGY PROOF: rebuild a specimen circle-profile solid
    (the sample .rfa's 4-leg extrusion 614: 10 faces, 24 edges, 16 loops)
    from its circles / offsets / numbering facts and compare against the
    specimen's own decoded GElement -- the specimen with its material
    surface FILLINGS stripped (cache state our solids do not carry).

    Verdict fields: ``structurally_exact`` (every class / pid / weakref /
    int / flag / count identical), ``geometry_max_float_dev`` (frames,
    CylSurf params, all coedge uv incl. every interior tessellation point
    -- expected ~1e-16), and the SEPARATE ``envelope_max_dev`` class: the
    cap/loop ``m_Envelope`` corners, which Revit computes from a finer
    display tessellation than the stored 7/6-chord edge points (~1e-4 ft
    where a chord misses the circle's extreme) [H irrelevant to
    acceptance, like the box's volatile GInfo bit].
    """
    from ..families import _index
    idx = _index(doc)
    sp = specimen_cylinder_inputs(idx, unit, extrusion_id)
    circles = [circle_profile(c["center"], c["radius"]) for c in sp["circles"]]
    ours = solid_cylinder_brep(
        circles, sp["start"], sp["end"], element_id=sp["element_id"],
        geometry_style_id=sp["geometry_style_id"],
        control_command=sp["control_command"],
        tag_bases=sp["tag_bases"], u_shifts=sp["u_shifts"],
        render_style_id=INVALID, tess_version=sp["tess_version"])
    theirs = _strip_fillings(sp["specimen_rep"])
    # ftol < 0 => every float leaf is reported with its deviation
    cmp = compare_object_trees(ours, theirs, ftol=-1.0)

    def _dev(entry: str) -> float:
        try:
            return float(entry.rsplit("(dev ", 1)[1].rstrip(")"))
        except Exception:                              # pragma: no cover
            return float("inf")

    env_devs = [d for d in cmp["float_devs_over_tol"] if ".m_Envelope." in d]
    geo_devs = [d for d in cmp["float_devs_over_tol"] if ".m_Envelope." not in d]
    env_max = max((_dev(d) for d in env_devs), default=0.0)
    geo_max = max((_dev(d) for d in geo_devs), default=0.0)
    geo_over = [d for d in geo_devs if _dev(d) > 1e-9]
    return {
        "extrusion_id": extrusion_id,
        "inputs": {k: sp[k] for k in ("circles", "start", "end", "tag_bases",
                                      "u_shifts", "geometry_style_id",
                                      "control_command", "tess_version")},
        "n_faces": len(ours["m_subNodes"][0]["value"]["m_pFaces"]),
        "n_edges": len(ours["m_subNodes"][0]["value"]["m_pEdges"]),
        "structural_mismatches": cmp["structural_mismatches"],
        "structurally_exact": not cmp["structural_mismatches"],
        "n_leaves": cmp["n_leaves"],
        "n_envelope_leaves": len(env_devs),
        "n_geometry_leaves": len(geo_devs),
        "geometry_max_float_dev": geo_max,      # frames, surfaces, all uv points
        "geometry_devs_over_1e9": geo_over[:10],
        "geometry_exact": not geo_over,
        "envelope_max_dev": env_max,              # cap/loop envelope corners only
        "envelope_within_tol": env_max <= env_tol,
        "ok": (not cmp["structural_mismatches"]) and (not geo_over)
              and env_max <= env_tol,
    }


# ---------------------------------------------------------------------------
# emission: splice a form into a donor .rfa (the acceptance-proof route)
# ---------------------------------------------------------------------------

_ELEMREC = struct.Struct("<qIIIqqI")     # 40-byte ElemRec [V stream_encoders]
_ET_FOOTER = struct.Struct("<IHHqI")      # marker, class, pad, last_id, zero (20 B)
PART_HDR_COUNT_OFF = 14                   # u32 elem_table_count in the stream header


def _elemtable_append(payload: bytes, new_rows: List[Tuple[int, int, int, int, int, int, int]]
                      ) -> Tuple[bytes, dict]:
    """Append ElemRec rows to an inflated ``Global/ElemTable`` payload,
    preserving a family file's GRAVEYARD tail (u32 count + 32-byte deleted
    records, which the project decoder does not model) verbatim, and
    raising the footer watermark.  Row layout (40 B):
    (original_id, creation_ep, modified_ep, user_modified_ep, id, owner_id,
    partition_id). [structure V: .rfa footer = u32 graveyard_count + n*32 B
    + u32 marker + u16 class + u16 pad + u64 last_id + u32 0]
    """
    from ..elemtable import parse_elemtable
    t = parse_elemtable(payload)
    head = payload[:6]
    n = t.count
    recs = payload[6:6 + 40 * n]
    tail = payload[6 + 40 * n:]                  # graveyard block + 20-byte footer
    if len(tail) < 20:
        raise ValueError(f"ElemTable tail too short ({len(tail)} B)")
    graveyard, footer = tail[:-20], tail[-20:]
    marker, tclass, pad, last_id, zero = _ET_FOOTER.unpack(footer)
    if marker != 0xFFFFFFFF:
        raise ValueError(f"unexpected ElemTable footer marker {marker:#x}")
    ids = sorted(t.records, key=lambda r: r.id)
    if new_rows and min(r[4] for r in new_rows) <= ids[-1].id:
        raise ValueError("new element ids must exceed the current watermark")
    body = bytearray(recs)
    for row in sorted(new_rows, key=lambda r: r[4]):
        body += _ELEMREC.pack(*[int(x) for x in row])
    new_count = n + len(new_rows)
    new_last = max(last_id, max(r[4] for r in new_rows)) if new_rows else last_id
    new_head = struct.pack("<HI", struct.unpack_from("<H", head, 0)[0], new_count)
    if len(head) != 6 or struct.unpack_from("<I", head, 2)[0] != n:
        # header layout differs from the model: keep bytes, patch the count in place
        new_head = bytearray(head)
        struct.pack_into("<I", new_head, 2, new_count)
        new_head = bytes(new_head)
    out = bytes(new_head) + bytes(body) + graveyard + _ET_FOOTER.pack(
        marker, tclass, pad, new_last, zero)
    return out, {"count_before": n, "count_after": new_count,
                 "watermark_before": last_id, "watermark_after": new_last,
                 "graveyard_bytes": len(graveyard)}


def emit_form_rfa(donor_rfa: str, out_path: str, bundles: Sequence[FormBundle],
                  *, level: int = 3, episode: Optional[int] = None) -> dict:
    """Author FORM elements into a donor family and write the ``.rfa``.

    The bundles' records (seq 101/102/103 per element) are appended to the
    single save unit of the donor's ``Partitions/<N>`` (immediately before
    each per-seq sentinel, block counters recomputed, every block re-gzipped
    with our writer, real CRCIO ECC), their ``ElemRec`` rows are appended
    to ``Global/ElemTable`` (family graveyard tail preserved), the partition
    header count is bumped and the container is rebuilt by our CFB writer.
    Everything else (the donor's identity, ``PartAtom``, ``Global/Latest``)
    is copied unchanged -- exactly the minimal-commit posture that Autodesk
    accepted for created project elements (KNOWLEDGE.md V20).
    """
    import dataclasses as _dc
    from .. import ecc
    from ..cfb_writer import write_cfb
    from ..container import open_rvt
    from ..encode import ObjectEncoder
    from ..partitions import StreamWalker, record_header_len
    from ..roundtrip import read_entries
    from ..stream_encoders import global_prefix
    from ..writer import BLOCK_TRL_TAG, gzip_member
    from ..families import FamilyIndex

    idx = FamilyIndex(donor_rfa)
    enc = ObjectEncoder(idx.schema)
    elements: List[SkelElement] = [e for b in bundles for e in b.elements]
    # -- serialize records ---------------------------------------------------
    def cid(name: str) -> int:
        return enc.class_id_of(name)
    recs_by_element: List[Dict[int, bytes]] = []
    for el in elements:
        out = {}
        for seq, cname, obj in el.records(by_name=True):
            k = cid(cname)
            if seq == 101:
                out[seq] = enc.encode_record(seq, el.elem_id, 0, k, obj)
            else:
                body = enc.encode_object(k, obj or {})
                from ..encode import record_stamp
                stamp = record_stamp(k, body)
                ps = 2 + len(body)
                out[seq] = (struct.pack("<qII", el.elem_id, stamp, ps)
                            + struct.pack("<H", k) + body + struct.pack("<I", ps))
        recs_by_element.append(out)

    entries = read_entries(donor_rfa)
    new_streams: Dict[str, bytes] = {}
    report: dict = {"donor": donor_rfa, "out": out_path,
                    "new_ids": [e.elem_id for e in elements],
                    "bundles": [b.kind for b in bundles]}
    with open_rvt(donor_rfa) as doc:
        parts = doc.partition_streams()
        if len(parts) != 1:
            raise NotImplementedError(f"expected one partition stream, got {parts}")
        pname = parts[0]
        # -- ElemTable -------------------------------------------------------
        et_payload = doc.inflate("Global/ElemTable")
        from ..elemtable import parse_elemtable
        t = parse_elemtable(et_payload)
        ep = int(episode) if episode is not None else max(r.modified_ep for r in t.records)
        rows = [(e.elem_id, ep, ep, ep, e.elem_id,
                 int(e.owner_id) if e.owner_id >= 0 else -1, 0) for e in elements]
        et_new, et_report = _elemtable_append(et_payload, rows)
        et_logical = global_prefix("Global/ElemTable") + gzip_member(et_new, level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)
        report["elemtable"] = et_report
        report["episode"] = ep
        # -- Partitions/<N>: append before each seq sentinel ------------------
        logical = doc.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"walker errors on donor: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        last_by_seq: Dict[int, Any] = {}
        for b in blocks:
            if b.unit == 0:
                last_by_seq[b.seq] = b
        added_bytes: Dict[int, int] = {}
        overrides: Dict[int, Tuple[bytes, int]] = {}
        for seq in (101, 102, 103):
            if seq not in last_by_seq:
                raise RuntimeError(f"donor unit 0 has no seq-{seq} block")
            b = last_by_seq[seq]
            payload = b.data
            ins = _sentinel_offset(payload, seq)
            extra = b"".join(r[seq] for r in recs_by_element)
            overrides[b.index] = (payload[:ins] + extra + payload[ins:], len(recs_by_element))
            added_bytes[seq] = len(extra)
        buf = bytearray()
        cursor = 0
        _ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}
        for b in blocks:
            payload, add_recs = overrides.get(b.index, (b.data, 0))
            buf += logical[cursor:b.member_offset]
            hdr = len(buf) - (b.member_offset - b.hdr_offset)
            gz = gzip_member(payload, level=level, sync_flush=True)
            nb = 8 + len(gz)
            struct.pack_into("<I", buf, hdr + 10, nb)                       # B
            if add_recs:
                a_new = b.n_records + add_recs
                # ISIZE identity (validator / rvt.partitions.Block.intended_len):
                # inflated == record_header_len(seq)*A + C + adj(flags), where
                # the counted header is the FULL record header (seq101 = 16 B,
                # seq102/103 = 20 B incl. the u32 psize repeat) -- NOT the
                # sentinel-record layout (_hdr_len).  commit.py uses the same
                # convention; using _hdr_len here left C 4*A too high and the
                # validator flagged the touched blocks (writer counter defect,
                # tolerated by Revit but wrong).
                c_new = (len(payload) - record_header_len(b.seq) * a_new
                         - _ISIZE_ADJ.get(b.flags, 0))
                struct.pack_into("<I", buf, hdr + 6, a_new)                # A
                struct.pack_into("<I", buf, hdr + 14, c_new)               # C
            buf += gz + struct.pack("<HI", BLOCK_TRL_TAG, nb)
            cursor = b.member_offset + b.member_len + 6
        buf += logical[cursor:]
        struct.pack_into("<I", buf, PART_HDR_COUNT_OFF, et_report["count_after"])
        w2 = StreamWalker(bytes(buf), inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after splice: {w2.errors[:3]}")
        part_logical = bytes(buf[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)
        report["partition"] = pname
        report["bytes_added_per_seq"] = added_bytes
    out_entries = [_dc.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    write_cfb(out_path, out_entries)
    report["size"] = os.path.getsize(out_path)
    report["verify"] = verify_emitted(out_path, donor_rfa, [e.elem_id for e in elements])
    return report


def _hdr_len(seq: int) -> int:
    return 12 if seq == 101 else 16


def _sentinel_offset(payload: bytes, seq: int) -> int:
    """Offset of the trailing save-unit sentinel record (id -1, psize 0)."""
    sl = _hdr_len(seq) + 4
    off = len(payload) - sl
    if off < 0:
        raise ValueError(f"seq {seq}: block too small for a sentinel")
    if seq == 101:
        eid, ps = struct.unpack_from("<qI", payload, off)
    else:
        eid, _st, ps = struct.unpack_from("<qII", payload, off)
    rep = struct.unpack_from("<I", payload, len(payload) - 4)[0]
    if not (eid == -1 and ps == 0 and rep == 0):
        raise ValueError(f"seq {seq}: block does not end with a sentinel")
    return off


def verify_emitted(path: str, donor: Optional[str], expect_ids: Sequence[int]) -> dict:
    """Read an emitted .rfa back: CRC/ECC/walker health (families.verify_rfa),
    the new elements decode clean in all three seqs, and the document keeps
    every donor id."""
    from ..families import verify_rfa, FamilyIndex
    from ..objects import iter_records
    rep = verify_rfa(path)
    idx = FamilyIndex(path)
    found = {}
    recs = idx.unit_records(0)
    for eid in expect_ids:
        row = {}
        for seq in (101, 102, 103):
            r = recs.get(seq, {}).get(eid)
            if r is None:
                row[seq] = "MISSING"
                continue
            o = idx.decode(0, eid, seq)
            row[seq] = {"class": idx.class_name(r.class_id),
                        "clean": bool(o and o.clean), "psize": r.body_size}
        found[eid] = row
    rep["new_elements"] = found
    rep["new_all_clean"] = all(
        isinstance(v, dict) and v["clean"] for row in found.values() for v in row.values())
    if donor:
        didx = FamilyIndex(donor)
        drecs = didx.unit_records(0)
        rep["donor_ids_preserved"] = all(
            set(drecs.get(s, {})) <= set(recs.get(s, {})) for s in (101, 102, 103))
        rep["record_counts_donor"] = {str(s): len(drecs.get(s, {})) for s in (101, 102, 103)}
    rep["record_counts_out"] = {str(s): len(recs.get(s, {})) for s in (101, 102, 103)}
    rep["ok"] = bool(rep.get("ok")) and rep["new_all_clean"] and rep.get("donor_ids_preserved", True)
    return rep


def validate_parity(path: str, donor: str) -> dict:
    """Run rvt.validate on the emitted file AND its donor and report the
    NEW findings (an untouched Autodesk .rfa already reports 5 baseline
    'errors' that are validator gaps for family files -- docs/inbox/
    families.md).  Parity = no error beyond the donor's own baseline."""
    from ..validate import validate_file

    def sigs(p):
        r = validate_file(p)
        errs = {(f.layer, f.message) for f in r.errors}
        return r, errs

    dr, dset = sigs(donor)
    orep, oset = sigs(path)
    new = sorted(f"{a}: {b}" for a, b in (oset - dset))
    keys = ("records", "elements_decoded", "decode_failures", "refs_checked",
            "gzip_members", "pages_checked")
    return {"donor_errors": len(dset), "out_errors": len(oset),
            "errors_beyond_baseline": new,
            "parity": not new,
            "out_stats": {k: orep.stats.get(k) for k in keys},
            "donor_stats": {k: dr.stats.get(k) for k in keys}}


# ---------------------------------------------------------------------------
# demo / proof driver
# ---------------------------------------------------------------------------

class _Ids:
    """id allocator continuing a donor document's watermark."""

    def __init__(self, start: int):
        self._n = int(start)

    def next(self) -> int:
        v = self._n
        self._n += 1
        return v


def _donor_watermark(donor: str) -> int:
    from ..container import open_rvt
    from ..elemtable import parse_elemtable
    with open_rvt(donor) as f:
        payload = f.inflate("Global/ElemTable")
    tail = payload[-20:]
    marker, _cl, _pad, last_id, _z = _ET_FOOTER.unpack(tail)
    if marker != 0xFFFFFFFF:
        t = parse_elemtable(payload)
        last_id = max(r.id for r in t.records)
    return int(last_id)


def build_proof_families(donor: str = SAMPLE_RFA, out_dir: str = OUT_DIR) -> dict:
    """Build the acceptance-proof families:

    * ``G_box_solid.rfa`` / ``G_box_dummy.rfa`` -- the donor + OUR box
      form (sketch on the Ref. Level, 4 curve elems, extrusion) carrying
      OUR authored six-face solid / a ``SerializedDummy`` rep;
    * ``G_cyl_solid.rfa`` / ``G_cyl_dummy.rfa`` -- the donor + OUR
      cylinder form (two half-arc curve elems, arc profile extrusion)
      carrying OUR authored CylSurf solid / a dummy rep.

    The box is a 500 x 300 x 700 mm cabinet, the cylinder a recessed-can
    sized 6 in (152 mm) dia x 190 mm; both placed clear of the donor's
    own table geometry.  The solid/dummy PAIRS answer the F4 regeneration
    question in the Revit acceptance gate.
    """
    os.makedirs(out_dir, exist_ok=True)
    ctx = context_from_rfa(donor)
    wm = _donor_watermark(donor)
    report = {"donor": donor, "context": ctx.__dict__, "watermark": wm, "files": {}}
    builders = {
        "box": lambda ids, rep: box(mm(500), mm(300), mm(700), ctx, ids,
                                    center=(mm(3000), 0.0), rep=rep),
        "cyl": lambda ids, rep: cylinder(inches(3), mm(190), ctx, ids,
                                         center=(mm(3000), mm(1000)), rep=rep),
    }
    for kind, builder in builders.items():
        for rep in (REP_SOLID, REP_DUMMY):
            ids = _Ids(wm + 1)
            fb = builder(ids, rep)
            rt = fb.roundtrip()
            out = os.path.join(out_dir, f"G_{kind}_{'solid' if rep == REP_SOLID else 'dummy'}.rfa")
            er = emit_form_rfa(donor, out, [fb])
            vp = validate_parity(out, donor)
            report["files"][os.path.basename(out)] = {
                "kind": fb.kind, "rep": rep, "ids": fb.ids, "params": fb.params,
                "schema_roundtrip_ok": rt["ok"],
                "emit": {k: v for k, v in er.items() if k not in ("verify",)},
                "verify": er["verify"], "validate": vp,
            }
    return report


def build_topology_proof(project: str = "rmebasicsampleproject",
                         rfa: str = SAMPLE_RFA) -> dict:
    """Reproduce BOTH specimen box solids (rme panelboard family, save
    unit 243, extrusions 786837 / 786867) AND the 4-leg cylinder solid
    (sample .rfa extrusion 614) from their dimensions."""
    out = {"specimens": {}, "cylinder_specimen": {}}
    for eid in (786837, 786867):
        try:
            out["specimens"][eid] = reproduce_specimen_solid(project, 243, eid)
        except Exception as exc:                    # pragma: no cover
            out["specimens"][eid] = {"error": repr(exc)}
    out["all_structurally_exact_modulo_volatile_bit"] = all(
        s.get("structurally_exact_modulo_volatile_bit") for s in out["specimens"].values())
    out["all_canonical_byte_exact"] = all(
        s.get("canonical_byte_exact") for s in out["specimens"].values())
    try:
        out["cylinder_specimen"][614] = reproduce_specimen_cylinders(rfa, 0, 614)
    except Exception as exc:                        # pragma: no cover
        out["cylinder_specimen"][614] = {"error": repr(exc), "ok": False}
    out["cylinder_ok"] = bool(out["cylinder_specimen"][614].get("ok"))
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="famgen geometry proof driver")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--donor", default=SAMPLE_RFA)
    ap.add_argument("--no-emit", action="store_true", help="topology proof only")
    ns = ap.parse_args(argv)
    result: dict = {}
    topo = build_topology_proof()
    result["topology_proof"] = topo
    print("=== topology reproduction (specimen boxes rebuilt from dimensions) ===")
    for eid, s in topo["specimens"].items():
        if "error" in s:
            print(f"  {eid}: ERROR {s['error']}")
            continue
        print(f"  {eid}: structural={'EXACT' if s['structurally_exact'] else ('EXACT mod 0x200' if s['structurally_exact_modulo_volatile_bit'] else 'MISMATCH')} "
              f"({s['n_leaves']} leaves, {len(s['structural_mismatches'])} mismatches), "
              f"max float dev={s['max_float_dev']:.3g}, "
              f"canonical byte-exact @1e-{s['digits']}={s['canonical_byte_exact']} "
              f"({s['canonical_bytes_ours']} B)")
    cy = topo["cylinder_specimen"].get(614, {})
    if "error" in cy:
        print(f"  614 (cylinder legs): ERROR {cy['error']}")
    elif cy:
        print(f"  614 (4 cylinders, {cy['n_faces']} faces / {cy['n_edges']} edges): "
              f"structural={'EXACT' if cy['structurally_exact'] else 'MISMATCH'} "
              f"({cy['n_leaves']} leaves), geometry max dev={cy['geometry_max_float_dev']:.3g} "
              f"({cy['n_geometry_leaves']} leaves), envelope max dev={cy['envelope_max_dev']:.3g} "
              f"({cy['n_envelope_leaves']} corners, cache class) -> ok={cy['ok']}")
    if not ns.no_emit:
        fam = build_proof_families(ns.donor, ns.out_dir)
        result["families"] = fam
        print("=== proof families ===")
        for name, f in fam["files"].items():
            v = f["verify"]
            print(f"  {name}: ids {f['ids'][0]}..{f['ids'][-1]}, schema rt "
                  f"{'OK' if f['schema_roundtrip_ok'] else 'FAIL'}, size {f['emit']['size']}, "
                  f"crc_fail={v.get('gzip_crc_failures')} ecc_mismatch={v.get('ecc_mismatch')} "
                  f"new_clean={v.get('new_all_clean')} donor_ids_kept={v.get('donor_ids_preserved')} "
                  f"validate_parity={f['validate']['parity']} "
                  f"(new errors: {f['validate']['errors_beyond_baseline'] or 'none'})")
    os.makedirs(ns.out_dir, exist_ok=True)
    rpath = os.path.join(ns.out_dir, "G_report.json")
    with open(rpath, "w") as fh:
        json.dump(result, fh, indent=1, default=str)
    print(f"report -> {rpath}")
    ok = (topo["all_structurally_exact_modulo_volatile_bit"] and topo["all_canonical_byte_exact"]
          and topo.get("cylinder_ok", False))
    if not ns.no_emit:
        ok = ok and all(f["verify"].get("ok") for f in result["families"]["files"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# solid self-checks: the invariants a closed B-rep must satisfy
# ---------------------------------------------------------------------------

def check_solid(gelement: dict, *, expect_n: int | None = None) -> List[str]:
    """Return a list of problems with a built solid -- empty means sound.

    Added after a generated N-gon prism reached the owner's Revit with the
    validator green (issue #504): ``rvt_validate`` checks records and
    references, and knows nothing about whether a B-rep is a closed
    manifold.  These are the invariants that ARE computable from the solid
    alone, so no reference file and no Revit round-trip is needed:

    1. Euler characteristic  V - E + F = 2  (a prism has 2N vertices);
    2. every edge names exactly 2 faces, and every face is named by at
       least 3 edges;
    3. every face's edge loop CLOSES -- following ``m_next`` within that
       face returns to the EdgeLoop, visiting each of its edges once;
    4. every edge endpoint reconstructs to the SAME 3D point from both of
       its faces' (origin, xVec, yVec) frames -- i.e. the stored uv
       coordinates and the surface frames agree.

    A solid that passes all four can still be wrong in ways only Autodesk's
    reader can judge (hard rule 4), but it cannot be OPEN, self-inconsistent
    or mis-parametrised, which is what silently shipped before.
    """
    probs: List[str] = []
    try:
        geom = gelement["m_subNodes"][0]["value"]
        faces, edges = geom["m_pFaces"], geom["m_pEdges"]
    except (KeyError, IndexError, TypeError):
        return ["not a GElement with a Geometry subnode"]
    wr = lambda w: w["weakref"]                                   # noqa: E731
    epid = {e["pid"]: e for e in edges}
    frame = {}
    for f in faces:
        s = (f["value"].get("m_pSurf") or {}).get("value") or {}
        if "m_origin" in s:
            frame[f["pid"]] = (s["m_origin"], s["m_xVec"], s["m_yVec"])

    uses: Dict[int, int] = {}
    for e in edges:
        fl = e["value"]["m_pFace"]
        if len(fl) != 2:
            probs.append(f"edge {e['pid']} names {len(fl)} faces, expected 2")
        for w in fl:
            uses[wr(w)] = uses.get(wr(w), 0) + 1
    for f in faces:
        if uses.get(f["pid"], 0) < 3:
            probs.append(f"face {f['pid']} is bounded by "
                         f"{uses.get(f['pid'], 0)} edges, expected >= 3")

    if expect_n is not None:
        if len(faces) != expect_n + 2:
            probs.append(f"{len(faces)} faces, expected {expect_n + 2}")
        if len(edges) != 3 * expect_n:
            probs.append(f"{len(edges)} edges, expected {3 * expect_n}")
        if (2 * expect_n) - len(edges) + len(faces) != 2:
            probs.append(f"Euler V-E+F != 2 for a {expect_n}-gon prism")

    for f in faces:
        lp = f["value"].get("m_pFirstLoop") or {}
        if not lp:
            probs.append(f"face {f['pid']} has no edge loop")
            continue
        cur, seen, guard = wr(lp["value"]["m_next"]), [], 0
        limit = 4 * len(edges) + 8
        while cur != lp["pid"] and guard < limit:
            e = epid.get(cur)
            if e is None:
                probs.append(f"face {f['pid']} loop references unknown edge {cur}")
                break
            seen.append(cur)
            k = 0 if wr(e["value"]["m_pFace"][0]) == f["pid"] else 1
            cur = wr(e["value"]["m_next"][k])
            guard += 1
        else:
            if len(seen) != len(set(seen)):
                probs.append(f"face {f['pid']} loop revisits an edge")
            elif len(seen) != uses.get(f["pid"], 0):
                probs.append(f"face {f['pid']} loop walks {len(seen)} edges "
                             f"but {uses.get(f['pid'], 0)} name it")
            continue
        probs.append(f"face {f['pid']} edge loop does not close")

    worst = 0.0
    for e in edges:
        ev = e["value"]
        if len(ev["m_pFace"]) != 2:
            continue
        for pt in ev["m_firstAndLastEdgePnts"]:
            xyz = []
            for k in (0, 1):
                fid = wr(ev["m_pFace"][k])
                if fid not in frame:
                    break
                o, x, y = frame[fid]
                u, v = pt["uv"][k]
                xyz.append([o[c] + u * x[c] + v * y[c] for c in range(3)])
            if len(xyz) == 2:
                worst = max(worst, max(abs(xyz[0][c] - xyz[1][c]) for c in range(3)))
    if worst > 1e-6:
        probs.append(f"edge endpoints disagree between their two faces by "
                     f"{worst:.3g} ft (uv / surface frame mismatch)")
    return probs

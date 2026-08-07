"""rvt.render.inspect -- the GEOMETRY-CARRIAGE inspector (LOAD vs RENDER lens).

For every element of a project it answers three questions the LOAD gate
never asked::

    * does the element carry BAKED (viewer-drawable) geometry?
    * how many bytes of it, in what form (solid B-rep / mesh / curves /
      an instance's reference to its symbol / nothing)?
    * where is it stored?

The answer to "where" is uniform: the drawable geometry of a Revit-saved
element is its **seq-103 record** in ``Partitions/<N>`` -- the per-element
"rep" stream that runs parallel to seq 101 (``ElementHeader``) and seq
102 (the element object).  The rep is one of:

``GElement`` (class 0x089e = ``GRep <- GGroup <- GNode``)
    a decoded scene-graph fragment.  Its sub-node tree is the BAKED
    geometry: ``Geometry`` (class 0x08fc, ``GBRep <- GNode``) = a B-rep
    solid (``m_pFaces`` -> ``Face`` {``EdgeLoop`` + analytic ``Surface``
    such as ``Plane`` + ``m_renderStyleId`` material}, ``m_pEdges`` ->
    ``Edge`` {two adjacent-face weakrefs, next/prev loop links, uv end
    points}); ``GLine``/``GArc`` symbolic curves; ``GPolyMesh`` meshes;
    ``GInstance`` = a placed reference to a symbol whose OWN rep carries
    the solid; ``GGroup``/``GFilter`` = grouping / conditional-visibility
    (``GFilter.m_oConditions`` = view-direction ``GConditionDir`` gates
    for the 2D symbolic sets; the 3D solid sits under an EMPTY-condition
    filter).  Its root carries ``m_bBox`` / ``m_tightbBox`` (feet),
    ``m_elementId`` and ``m_gElemType`` (3 = geometry element).
``SerializedDummy`` (class 0x0f2c, psize 2 = a bare class id)
    NOTHING to draw.  Legitimate for exactly two families of elements:
    non-geometric ones (settings / styles / annotation records, datum --
    levels and grids are drawn from PARAMETERS, circuits) and
    annotation-family instances (title blocks, tags, elevation marks --
    drawn from 2D family graphics in a view).  A 3D MODEL element with a
    dummy rep translates ("LOAD" passes) but is INVISIBLE: Autodesk's
    cloud viewer / RevitExtractor draws baked geometry only and does not
    regenerate.  Corpus law (5 samples, ~81,500 elements): 413/413
    native walls, every floor / ceiling / roof / duct / pipe / conduit /
    room carries a ``GElement`` B-rep; zero native 3D model elements are
    dummy.  Our created walls emitted ``SerializedDummy`` -- the entire
    reason they never rendered (docs/writer/baked-geometry.md).

Kinds reported (``ElementGeometry.kind``)::

    brep              record contains >= 1 ``Geometry`` node with faces
    mesh              record contains a ``GPolyMesh`` (imported / topo)
    instance-ref      record contains a ``GInstance`` (drawable BY
                      REFERENCE: the symbol's rep must itself carry brep)
    instance-ref+geom a ``GInstance`` PLUS embedded geometry (host-cut
                      doors/windows carry a per-host symbol-GRep clone)
    curves-only       only ``GLine``/``GArc``/``GPoint`` -- 2D-drawable
    empty-grep        a ``GElement`` with no drawable descendants
    dummy             ``SerializedDummy`` -- no baked geometry
    other:<Class>     an unexpected rep class
    no-record         no seq-103 record for the id
    undecodable       the rep did not decode (decoder error recorded)

Public API::

    row  = inspect_element(doc, element_id)      # one ElementGeometry
    rows = inspect(source)                       # every host element
    rows = inspect(source, classes=["SWall"])    # by seq-102 class name
    rows = inspect(source, ids=[493612])         # by id
    print(render_report(rows))                   # aligned text table
    summary(rows)                                # per-class / per-kind
    ref = resolve_instance_reference(doc, row)   # instance -> its symbol's row

``source`` = a :class:`rvt.mutate.Document`, a ``.rvt`` path, or a corpus
project name (``rstbasicsampleproject``).  CLI::

    python -m rvt.render.inspect <file.rvt|project>
        [--class SWall] [--id 493612] [--all] [--limit N] [--json out.json]
        [--faces]      # per-face plane / material dump for brep rows
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field as dc_field
from typing import Any, Iterable, Optional, Sequence, Union

from ..mutate import Document

# --- classes -----------------------------------------------------------------

#: seq-103 rep classes
CLASS_GELEMENT = 0x089E          # GRep <- GGroup <- GNode: baked scene graph
CLASS_SERIALIZED_DUMMY = 0x0F2C  # empty placeholder: NO baked geometry

#: G-node classes that ARE drawable solids / meshes / curves
_SOLID_CLASSES = frozenset({"Geometry"})                      # GBRep subclass
_MESH_CLASSES = frozenset({"GPolyMesh", "GMesh", "PolyFaceMeshFaces"})
_CURVE_CLASSES = frozenset({"GLine", "GArc", "GEllipse", "GNurbSpline",
                            "GPolyCurve", "GOffsetCurve", "GHermiteSpline",
                            "GCurve"})
_POINT_CLASSES = frozenset({"GPoint"})
_INSTANCE_CLASSES = frozenset({"GInstance"})
_GROUP_CLASSES = frozenset({"GGroup", "GFilter", "GElement", "GGTag",
                            "GBitmap", "GFilling"})

#: the storage statement, per kind
STORAGE_BREP = ("Partitions/<N> seq-103 record: class GElement (0x89e) -> "
                "Geometry (GBRep) faces/edges = baked B-rep solid")
STORAGE_REF = ("Partitions/<N> seq-103 record: class GElement (0x89e) -> "
               "GInstance = reference to the symbol's rep (geometry lives on the symbol)")
STORAGE_CURVES = ("Partitions/<N> seq-103 record: class GElement (0x89e) -> "
                  "GLine/GArc symbolic curves only (2D)")
STORAGE_MESH = ("Partitions/<N> seq-103 record: class GElement (0x89e) -> "
                "GPolyMesh tessellation")
STORAGE_DUMMY = ("Partitions/<N> seq-103 record: class SerializedDummy (0xf2c), "
                 "0-byte object -> NO baked geometry (desktop regenerates; the "
                 "cloud viewer/extractor does NOT)")
STORAGE_NONE = "no seq-103 record present for this id"


# --- data model --------------------------------------------------------------

@dataclass
class ElementGeometry:
    """The geometry-carriage verdict for one element."""
    element_id: int
    klass: Optional[str]            # seq-102 element class (e.g. 'SWall')
    rep_class: Optional[str]        # seq-103 record class ('GElement' / 'SerializedDummy')
    kind: str                       # see module docstring
    has_baked_geometry: bool        # True if drawable geometry is present (own or by reference)
    by_reference: bool = False      # True for instance-ref: the symbol's rep is the drawable
    drawable_3d: bool = False       # solid / mesh / instance-ref (a 3D-view drawable)
    geometry_bytes: int = 0         # seq-103 record payload size (psize)
    storage: str = STORAGE_NONE
    n_solids: int = 0
    n_faces: int = 0
    n_edges: int = 0
    n_curves: int = 0
    n_points: int = 0
    n_meshes: int = 0
    n_instances: int = 0
    surface_types: dict = dc_field(default_factory=dict)     # {'Plane': n, 'CylinderSurf': n, ...}
    render_style_ids: list = dc_field(default_factory=list)  # material element ids on faces
    bbox: Optional[list] = None     # GRep.m_bBox [[minx,miny,minz],[maxx,maxy,maxz]] feet
    gelem_type: Optional[int] = None
    category_id: Optional[int] = None       # header m_categroryId
    symbol_id: Optional[int] = None         # instances: the master symbol referenced
    notes: list = dc_field(default_factory=list)

    def to_json(self) -> dict:
        d = asdict(self)
        return d

    def line(self) -> str:
        geo = ""
        if self.kind.startswith("instance-ref"):
            geo = f"-> symbol {self.symbol_id}"
        elif self.n_solids or self.n_meshes:
            geo = (f"solids={self.n_solids} faces={self.n_faces} edges={self.n_edges} "
                   f"meshes={self.n_meshes} curves={self.n_curves}")
        elif self.n_curves or self.n_points:
            geo = f"curves={self.n_curves} points={self.n_points}"
        return (f"{self.element_id:>10d}  {str(self.klass or '?'):26s} "
                f"{self.kind:18s} baked={'YES' if self.has_baked_geometry else 'no ':3s}"
                f"{'(ref)' if self.by_reference else '     '} "
                f"{self.geometry_bytes:9d} B  {geo}")


# --- source normalisation -----------------------------------------------------

def _open(source: Union[str, "Document"]) -> Document:
    """A Document from a corpus project name, a .rvt path, or a Document."""
    if isinstance(source, Document):
        return source
    if isinstance(source, str):
        if source.lower().endswith((".rvt", ".rte", ".rfa")) or os.sep in source:
            return Document.from_file(source)
        return Document.load(source)
    raise TypeError(f"unsupported source {type(source)!r}")


def _ptr(x: Any):
    """Unwrap a decoded pointer holder -> (class_name, value) or (None, None)."""
    if isinstance(x, dict) and "ptr_class" in x:
        return x["ptr_class"], x.get("value")
    return None, None


# --- the walker -----------------------------------------------------------------

@dataclass
class _Carriage:
    solids: int = 0
    faces: int = 0
    edges: int = 0
    curves: int = 0
    points: int = 0
    meshes: int = 0
    instances: int = 0
    surfaces: Counter = dc_field(default_factory=Counter)
    styles: set = dc_field(default_factory=set)


def _walk_gnode(cname: Optional[str], value: Any, c: _Carriage, depth: int = 0) -> None:
    """Depth-first census of a decoded G-node tree (a seq-103 GElement value)."""
    if depth > 64 or cname is None or not isinstance(value, dict):
        return
    if cname in _SOLID_CLASSES:
        faces = value.get("m_pFaces") or []
        edges = value.get("m_pEdges") or []
        c.solids += 1
        c.faces += len(faces)
        c.edges += len(edges)
        for f in faces:
            _, fv = _ptr(f)
            if not isinstance(fv, dict):
                continue
            sc, _sv = _ptr(fv.get("m_pSurf"))
            c.surfaces[sc or "None"] += 1
            rs = fv.get("m_renderStyleId")
            if isinstance(rs, int) and rs not in (-1,):
                c.styles.add(rs)
    elif cname in _MESH_CLASSES:
        c.meshes += 1
    elif cname in _CURVE_CLASSES:
        c.curves += 1
    elif cname in _POINT_CLASSES:
        c.points += 1
    elif cname in _INSTANCE_CLASSES:
        c.instances += 1
        # a GInstance may embed a per-host clone of its symbol's geometry
        ec, ev = _ptr(value.get("m_oEmbeddedSymbolGRep"))
        _walk_gnode(ec, ev, c, depth + 1)
    for sn in value.get("m_subNodes") or []:
        sc, sv = _ptr(sn)
        _walk_gnode(sc, sv, c, depth + 1)


def _classify(rep_class: Optional[str], c: _Carriage) -> str:
    if rep_class is None:
        return "no-record"
    if rep_class == "SerializedDummy":
        return "dummy"
    if rep_class != "GElement":
        return f"other:{rep_class}"
    if c.instances:
        return "instance-ref+geom" if (c.faces or c.meshes) else "instance-ref"
    if c.solids and c.faces:
        return "brep"
    if c.meshes:
        return "mesh"
    if c.curves or c.points:
        return "curves-only"
    if c.solids and not c.faces:
        return "empty-grep"      # a Geometry node with no faces (Revit stubs these)
    return "empty-grep"


_STORAGE_BY_KIND = {
    "brep": STORAGE_BREP,
    "mesh": STORAGE_MESH,
    "instance-ref": STORAGE_REF,
    "instance-ref+geom": STORAGE_REF,
    "curves-only": STORAGE_CURVES,
    "dummy": STORAGE_DUMMY,
    "empty-grep": ("Partitions/<N> seq-103 record: class GElement (0x89e) with NO "
                   "drawable descendants"),
    "no-record": STORAGE_NONE,
}


def _instance_symbol(doc: Document, eid: int) -> Optional[int]:
    """The symbol a placed instance references (m_masterSymbolId, else the
    InstanceInfo symbol), when decodable."""
    try:
        v = doc.value(eid, 102)
    except Exception:
        return None
    if not isinstance(v, dict):
        return None
    sid = v.get("m_masterSymbolId")
    if isinstance(sid, int) and sid > 0:
        return sid
    ii = ((v.get("m_pInstanceInfo") or {}).get("value") or {})
    sid = ii.get("m_symbolId")
    return sid if isinstance(sid, int) and sid > 0 else None


def inspect_element(doc: Document, element_id: int) -> ElementGeometry:
    """Geometry carriage of ONE element of ``doc`` (any :class:`Document`)."""
    r103 = doc.record(element_id, 103)
    r102 = doc.record(element_id, 102)
    klass = doc.dec.class_name(r102.class_id) if r102 is not None else None
    if r103 is None:
        return ElementGeometry(element_id, klass, None, "no-record", False,
                               storage=STORAGE_NONE,
                               notes=["element has no seq-103 rep record"])
    rep_class = doc.dec.class_name(r103.class_id)
    row = ElementGeometry(element_id, klass, rep_class, "?", False,
                          geometry_bytes=int(r103.body_size))
    # header category (cheap; the ElementHeader is small)
    try:
        row.category_id = doc.category_of(element_id)
    except Exception:
        row.category_id = None

    if rep_class == "SerializedDummy":
        row.kind = "dummy"
        row.storage = STORAGE_DUMMY
        row.notes.append("no baked geometry: desktop Revit regenerates on open; "
                         "the cloud viewer's extractor does NOT -> invisible")
        return row
    if rep_class != "GElement":
        row.kind = f"other:{rep_class}"
        row.storage = f"Partitions/<N> seq-103 record: class {rep_class}"
        return row

    obj = doc.decode(element_id, 103)
    if obj is None or (obj.errors and not obj.value):
        row.kind = "undecodable"
        row.storage = "seq-103 record present but not decodable"
        if obj is not None:
            row.notes.append(f"decode error: {obj.errors[:1]}")
        return row
    if obj.errors:
        row.notes.append(f"partial decode: {obj.errors[0].get('error')}")
    v = obj.value
    c = _Carriage()
    _walk_gnode("GElement", v, c)
    row.kind = _classify("GElement", c)
    row.n_solids, row.n_faces, row.n_edges = c.solids, c.faces, c.edges
    row.n_curves, row.n_points, row.n_meshes = c.curves, c.points, c.meshes
    row.n_instances = c.instances
    row.surface_types = dict(c.surfaces)
    row.render_style_ids = sorted(c.styles)
    row.bbox = v.get("m_bBox") if isinstance(v, dict) else None
    row.gelem_type = v.get("m_gElemType") if isinstance(v, dict) else None
    row.storage = _STORAGE_BY_KIND.get(row.kind, STORAGE_BREP)
    row.has_baked_geometry = row.kind in ("brep", "mesh", "curves-only",
                                          "instance-ref", "instance-ref+geom")
    row.by_reference = row.kind.startswith("instance-ref")
    row.drawable_3d = row.kind in ("brep", "mesh", "instance-ref", "instance-ref+geom")
    if row.by_reference:
        row.symbol_id = _instance_symbol(doc, element_id)
        row.notes.append("drawable BY REFERENCE: the referenced symbol's own "
                         "rep must carry the solid (resolve_instance_reference)")
    if row.kind == "curves-only":
        row.notes.append("symbolic curves only: 2D-drawable, no 3D solid")
    if row.kind == "empty-grep":
        row.notes.append("GElement with no drawable descendants")
    return row


def resolve_instance_reference(doc: Document, row: ElementGeometry) -> Optional[ElementGeometry]:
    """For an ``instance-ref`` row, inspect the SYMBOL it references (the
    geometry an instance draws lives on its symbol's rep).  Returns the
    symbol's :class:`ElementGeometry`, or ``None`` if unresolvable."""
    if not row.by_reference or not row.symbol_id:
        return None
    try:
        return inspect_element(doc, row.symbol_id)
    except Exception:
        return None


def inspect(source: Union[str, Document], *, classes: Optional[Sequence[str]] = None,
            ids: Optional[Sequence[int]] = None, host_only: bool = True,
            limit: Optional[int] = None) -> list[ElementGeometry]:
    """Inspect elements of ``source`` (project name / .rvt path / Document).

    ``ids`` -- exact element ids; ``classes`` -- seq-102 class names
    (``["SWall", "FamilyInstance"]``); neither -> EVERY host-document
    element that owns a seq-103 record.  ``host_only`` keeps to the host
    document (unit 0 = ``Global/ElemTable`` ids), excluding embedded family
    documents; ``limit`` caps the row count.
    """
    doc = _open(source)
    if ids:
        want = list(ids)
    elif classes:
        want = []
        for cname in classes:
            want.extend(doc.ids_of_class(cname, host_only=host_only))
        want = sorted(set(want))
    else:
        want = sorted(doc.idx[103])
        if host_only:
            want = [i for i in want if i in doc.et_by_id]
    if limit:
        want = want[:limit]
    return [inspect_element(doc, eid) for eid in want]


# --- reporting -------------------------------------------------------------------

def summary(rows: Iterable[ElementGeometry]) -> dict:
    """Per-class x per-kind counts + totals."""
    per_class: dict = defaultdict(Counter)
    kinds: Counter = Counter()
    baked = 0
    total = 0
    bytes_total = 0
    for r in rows:
        per_class[r.klass or "?"][r.kind] += 1
        kinds[r.kind] += 1
        baked += bool(r.has_baked_geometry)
        total += 1
        bytes_total += r.geometry_bytes
    return {
        "elements": total,
        "with_baked_geometry": baked,
        "without_baked_geometry": total - baked,
        "geometry_bytes_total": bytes_total,
        "kinds": dict(kinds),
        "per_class": {k: dict(v) for k, v in per_class.items()},
    }


def render_report(rows: Sequence[ElementGeometry], header: bool = True) -> str:
    lines = []
    if header:
        lines.append(f"{'element':>10s}  {'class':26s} {'rep kind':18s} baked      "
                     f"{'bytes':>9s}     detail")
        lines.append("-" * 118)
    for r in rows:
        lines.append(r.line())
    s = summary(rows)
    lines.append("-" * 118)
    lines.append(f"{s['elements']} elements: {s['with_baked_geometry']} carry baked/"
                 f"referenced geometry, {s['without_baked_geometry']} do not; "
                 f"seq-103 bytes {s['geometry_bytes_total']}")
    lines.append("kinds: " + ", ".join(f"{k}={v}" for k, v in sorted(s["kinds"].items(),
                                                                     key=lambda kv: -kv[1])))
    return "\n".join(lines)


def render_class_summary(rows: Sequence[ElementGeometry]) -> str:
    s = summary(rows)
    out = [f"{'class':30s} rep kinds"]
    out.append("-" * 78)
    per = s["per_class"]
    for cname in sorted(per, key=lambda k: -sum(per[k].values())):
        out.append(f"{cname:30s} {per[cname]}")
    return "\n".join(out)


def face_report(doc: Document, element_id: int) -> str:
    """Per-face plane / material dump of every solid in an element's rep --
    the byte-level 'what is drawn' view (see docs/writer/baked-geometry.md)."""
    obj = doc.decode(element_id, 103)
    if obj is None:
        return f"element {element_id}: no seq-103 record"
    if doc.dec.class_name(doc.record(element_id, 103).class_id) != "GElement":
        return f"element {element_id}: rep is not a GElement (no faces)"
    out = [f"element {element_id} baked solids:"]
    n = [0]

    def walk(cname, v, depth):
        if not isinstance(v, dict) or depth > 64:
            return
        if cname == "Geometry":
            n[0] += 1
            gi = v.get("m_GInfo") or {}
            out.append(f"  solid #{n[0]}: category(GStyle)={gi.get('m_categoryId')} "
                       f"faces={len(v.get('m_pFaces') or [])} "
                       f"edges={len(v.get('m_pEdges') or [])}")
            for f in v.get("m_pFaces") or []:
                _, fv = _ptr(f)
                if not isinstance(fv, dict):
                    continue
                fgi = fv.get("m_GInfo") or {}
                sc, sv = _ptr(fv.get("m_pSurf"))
                sv = sv or {}
                o = sv.get("m_origin")
                x = sv.get("m_xVec")
                y = sv.get("m_yVec")
                nrm = _cross(x, y) if (x and y) else None
                if nrm is not None and sv.get("m_orientFlag") is False:
                    nrm = [-t for t in nrm]
                env = ((sv.get("m_Envelope") or {}).get("m_corners"))
                out.append(f"      face tag={fgi.get('m_tag')} {sc} "
                           f"origin={_fmt3(o)} normal={_fmt3(nrm)} "
                           f"uv_env={env} material={fv.get('m_renderStyleId')} "
                           f"cutType={fv.get('m_cutType')}")
        for sn in v.get("m_subNodes") or []:
            sc, sv = _ptr(sn)
            if sc:
                walk(sc, sv, depth + 1)
        ec, ev = _ptr(v.get("m_oEmbeddedSymbolGRep"))
        if ec:
            walk(ec, ev, depth + 1)

    walk("GElement", obj.value, 0)
    if n[0] == 0:
        out.append("  (no Geometry solids in this rep)")
    return "\n".join(out)


def _cross(a, b):
    try:
        return [a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0]]
    except Exception:
        return None


def _fmt3(v):
    if not v:
        return None
    try:
        return [round(float(t), 4) for t in v]
    except Exception:
        return v


def to_json_rows(rows: Sequence[ElementGeometry]) -> dict:
    return {"summary": summary(rows), "rows": [r.to_json() for r in rows]}


# --- CLI ------------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    source = argv[0]
    classes: list = []
    ids: list = []
    json_out = None
    limit = None
    show_faces = False
    show_all = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--class" and i + 1 < len(argv):
            classes.append(argv[i + 1]); i += 2
        elif a == "--id" and i + 1 < len(argv):
            ids.append(int(argv[i + 1])); i += 2
        elif a == "--json" and i + 1 < len(argv):
            json_out = argv[i + 1]; i += 2
        elif a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1]); i += 2
        elif a == "--faces":
            show_faces = True; i += 1
        elif a == "--all":
            show_all = True; i += 1
        else:
            print(f"unknown arg {a!r}"); return 2
    doc = _open(source)
    if not classes and not ids and not show_all:
        # default: the classes a genesis / creation stream cares about
        classes = ["SWall", "VWall", "FaceWall", "FamilyInstance",
                   "FamilySymbol", "Floor", "Ceiling", "Level", "Grid"]
    rows = inspect(doc, classes=classes or None, ids=ids or None, limit=limit)
    if len(rows) > 60 and not ids:
        print(render_class_summary(rows))
        s = summary(rows)
        print("-" * 78)
        print(f"{s['elements']} elements: {s['with_baked_geometry']} baked/referenced, "
              f"{s['without_baked_geometry']} without; kinds "
              + ", ".join(f"{k}={v}" for k, v in sorted(s["kinds"].items(), key=lambda kv: -kv[1])))
    else:
        print(render_report(rows))
        for r in rows:
            if r.by_reference:
                ref = resolve_instance_reference(doc, r)
                if ref is not None:
                    print(f"    -> instance {r.element_id} references symbol {r.symbol_id}: "
                          f"{ref.kind} ({ref.geometry_bytes} B, faces={ref.n_faces})")
    if show_faces:
        for r in rows:
            if r.kind == "brep":
                print()
                print(face_report(doc, r.element_id))
    if json_out:
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, "w") as fh:
            json.dump(to_json_rows(rows), fh, indent=1, default=str)
        print(f"\nwrote {len(rows)} rows -> {json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

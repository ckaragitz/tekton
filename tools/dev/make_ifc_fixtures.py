#!/usr/bin/env python3
"""tools/dev/make_ifc_fixtures.py -- generate tekton's OWN IFC conformance
fixtures (issue #154) and pin what the resolver does with them TODAY.

Every byte of every ``tests/ifc_conformance/*.ifc`` is written by THIS script
from the parameters below -- plain ISO-10303-21 text in the style of
``rvt.frontdoor.ifc_out._W``, stdlib only, deterministic (md5-seeded
GlobalIds, pinned header stamp).  Nothing is copied from any third-party
file (hard rule 3): the fixtures are authored, not sampled.

The fixtures are the shared, owned inputs of the IFC -> RVT issues (#152
extrusions, #153 census, #155 steplite foreign classes, #156 storeys, #157
walls, #158 spaces, #159 IFC2X3).  Each ``<name>.ifc`` has a sibling
``<name>.expected.json`` pinning the summary ``rvt.ifc.intent.resolve_intent``
yields for it under the stdlib ``steplite`` backend -- today's behaviour,
right or wrong, with the issue that will change it cited in ``notes`` -- so a
later PR flips an expectation deliberately instead of silently.

    python3 tools/dev/make_ifc_fixtures.py                    # (re)write the .ifc fixtures
    python3 tools/dev/make_ifc_fixtures.py --check            # exit 1 if a committed .ifc drifted from the generator
    python3 tools/dev/make_ifc_fixtures.py --update-expected  # re-pin .expected.json from today's steplite resolver
    python3 tools/dev/make_ifc_fixtures.py --list             # fixture table (name, size, pins)
    python3 tools/dev/make_ifc_fixtures.py --resolve A.ifc .. # (internal) print resolver summaries as JSON

``--resolve`` is the one place the engine is imported; the test module and
``--update-expected`` both call it in a subprocess so the backend is chosen
by the environment alone (``RVT_STEPLITE_FORCE=1`` = steplite even when a
real ifcopenshell is installed; unset = whichever ``import ifcopenshell``
finds).  Territory: this file, ``tests/ifc_conformance/**``,
``tests/test_ifc_conformance.py`` (ifc-conformance stream, #154).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_DIR = os.path.join(ROOT, "tests", "ifc_conformance")
GENERATOR = "tools/dev/make_ifc_fixtures.py"
HEADER_MARK = "hand-authored by tekton -- no third-party bytes"
MAX_BYTES = 20 * 1024

#: pinned header stamp: the generator is deterministic by construction
_STAMP = "2026-08-09T00:00:00"
_CREATED = 1786060800                    # IfcOwnerHistory.CreationDate (fixed)

#: IFC GlobalId base-64 alphabet
_G64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

#: 12 triangles of an 8-corner box (1-based, bottom ring 1-4, top ring 5-8)
_TRIS = "((1,3,2),(1,4,3),(5,6,7),(5,7,8),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,4,8),(3,8,7),(4,1,5),(4,5,8))"
#: the same box as 6 quads (brep faces, outward winding not required by readers)
_QUADS = ((1, 4, 3, 2), (5, 6, 7, 8), (1, 2, 6, 5), (2, 3, 7, 6), (3, 4, 8, 7), (4, 1, 5, 8))


# ---------------------------------------------------------------------------
# STEP primitives
# ---------------------------------------------------------------------------

def _guid(seed: str) -> str:
    """Deterministic 22-char IFC GlobalId from a stable seed string."""
    n = int.from_bytes(hashlib.md5(seed.encode("utf-8")).digest(), "big")
    out = [_G64[(n >> 126) & 0x3]]
    for i in range(21):
        out.append(_G64[(n >> (120 - 6 * i)) & 0x3F])
    return "".join(out)


def _f(v: float) -> str:
    """STEP REAL: always a decimal point, never an exponent ('3.', '0.55')."""
    return f"{float(v):.6f}".rstrip("0")


def _s(v: Any) -> str:
    """STEP string literal (ASCII, quotes doubled)."""
    t = str(v).replace("'", "''")
    return "'" + t.encode("ascii", "replace").decode("ascii") + "'"


def _pt(p: Sequence[float]) -> str:
    return "(" + ",".join(_f(c) for c in p) + ")"


class Length(float):
    """A pset value written as IFCLENGTHMEASURE (project length units) rather
    than a unitless IFCREAL -- what a real exporter does for dimensions."""


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
# the model builder: project scaffolding + geometry + relationship helpers
# ---------------------------------------------------------------------------

class Model:
    """One fixture under construction: project -> site -> building scaffolding
    on creation, storeys / products / relations added by the builder.
    Coordinates are in the file's OWN length unit (``unit``: 'metre' |
    'milli' | 'foot'); nothing converts.  ``building`` = (location, x-dir) of
    a non-identity building placement under the site."""

    def __init__(self, name: str, *, schema: str = "IFC4", unit: str = "metre",
                 building: Optional[Tuple[Sequence[float], Sequence[float]]] = None) -> None:
        self.name = name
        self.schema = schema
        self.w = w = _W()
        self._contained: Dict[str, List[str]] = {}      # spatial ref -> products
        self._aggregated: Dict[str, List[str]] = {}     # whole ref -> parts
        self._storeys: List[str] = []
        person = w.add("IFCPERSON($,'tekton','fixtures',$,$,$,$,$)")
        org = w.add("IFCORGANIZATION($,'tekton',$,$,$)")
        po = w.add(f"IFCPERSONANDORGANIZATION({person},{org},$)")
        app = w.add(f"IFCAPPLICATION({org},'1.0','tekton conformance fixtures','tekton_fixtures')")
        self.oh = w.add(f"IFCOWNERHISTORY({po},{app},$,.NOCHANGE.,$,$,$,{_CREATED})")
        self.dirx = w.add("IFCDIRECTION((1.,0.,0.))")
        self.diry = w.add("IFCDIRECTION((0.,1.,0.))")
        self.dirz = w.add("IFCDIRECTION((0.,0.,1.))")
        origin = w.add("IFCCARTESIANPOINT((0.,0.,0.))")
        self.a2p0 = w.add(f"IFCAXIS2PLACEMENT3D({origin},{self.dirz},{self.dirx})")
        ctx = w.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{self.a2p0},$)")
        self.sub = w.add("IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,"
                         f"{ctx},$,.MODEL_VIEW.,$)")
        metre = w.add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)")
        if unit == "milli":
            length = w.add("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)")
        elif unit == "foot":
            dims = w.add("IFCDIMENSIONALEXPONENTS(1,0,0,0,0,0,0)")
            mwu = w.add(f"IFCMEASUREWITHUNIT(IFCLENGTHMEASURE(0.3048),{metre})")
            length = w.add(f"IFCCONVERSIONBASEDUNIT({dims},.LENGTHUNIT.,'FOOT',{mwu})")
        else:
            length = metre
        units = [length,
                 w.add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)"),
                 w.add("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)"),
                 w.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)")]
        ua = w.add(f"IFCUNITASSIGNMENT(({','.join(units)}))")
        project = w.add(f"IFCPROJECT({self.gid('project')},{self.oh},'tekton conformance fixture',"
                        f"$,$,$,$,({ctx}),{ua})")
        # one shared surface style for every solid
        rgb = w.add("IFCCOLOURRGB($,0.55,0.6,0.62)")
        rend = w.add(f"IFCSURFACESTYLERENDERING({rgb},0.,$,$,$,$,$,$,.NOTDEFINED.)")
        sstyle = w.add(f"IFCSURFACESTYLE('tekton_fixture_gray',.BOTH.,({rend}))")
        self.style = w.add(f"IFCPRESENTATIONSTYLEASSIGNMENT(({sstyle}))")
        # project -> site -> building
        plc_site = self.placement(None)
        site = w.add(f"IFCSITE({self.gid('site')},{self.oh},'Site',$,$,{plc_site},$,$,.ELEMENT.,$,$,$,$,$)")
        self.plc_building = self.placement(plc_site, self.axis(*building) if building else None)
        self.building = w.add(f"IFCBUILDING({self.gid('building')},{self.oh},'Building',$,$,"
                              f"{self.plc_building},$,$,.ELEMENT.,$,$,$)")
        self.aggregate(project, [site])
        self.aggregate(site, [self.building])

    # -- identifiers ---------------------------------------------------------
    def gid(self, seed: str) -> str:
        return _s(_guid(f"{self.name}:{seed}"))

    # -- placements ----------------------------------------------------------
    def axis(self, loc: Sequence[float], x: Sequence[float] = (1.0, 0.0, 0.0)) -> str:
        """An IfcAxis2Placement3D at ``loc`` with Z up and RefDirection ``x``
        (the shared identity one when trivial)."""
        if tuple(loc) == (0.0, 0.0, 0.0) and tuple(x) == (1.0, 0.0, 0.0):
            return self.a2p0
        p = self.w.add(f"IFCCARTESIANPOINT({_pt(loc)})")
        if tuple(x) == (1.0, 0.0, 0.0):
            dx = self.dirx
        elif tuple(x) == (0.0, 1.0, 0.0):
            dx = self.diry
        else:
            dx = self.w.add(f"IFCDIRECTION({_pt(x)})")
        return self.w.add(f"IFCAXIS2PLACEMENT3D({p},{self.dirz},{dx})")

    def placement(self, rel_to: Optional[str], a2p: Optional[str] = None) -> str:
        return self.w.add(f"IFCLOCALPLACEMENT({rel_to or '$'},{a2p or self.a2p0})")

    # -- spatial structure ---------------------------------------------------
    def storey(self, name: str, elevation: float) -> Tuple[str, str]:
        """(storey ref, its local placement) -- placed ``elevation`` above the
        building, ``Elevation`` attribute set to match."""
        plc = self.placement(self.plc_building, self.axis((0.0, 0.0, float(elevation))))
        sto = self.w.add(f"IFCBUILDINGSTOREY({self.gid('storey:' + name)},{self.oh},{_s(name)},$,$,"
                         f"{plc},$,$,.ELEMENT.,{_f(elevation)})")
        self._storeys.append(sto)
        return sto, plc

    def aggregate(self, whole: str, parts: Sequence[str]) -> None:
        self._aggregated.setdefault(whole, []).extend(parts)

    def contain(self, structure: str, products: Sequence[str]) -> None:
        self._contained.setdefault(structure, []).extend(products)

    # -- geometry --------------------------------------------------------------
    @staticmethod
    def box_pts(cx: float, cy: float, ax: float, ay: float, half_len: float,
                half_thick: float, zlo: float, zhi: float) -> List[Tuple[float, float, float]]:
        """8 corners of a plan-rotated box: centre, long axis (unit), half
        extents along / across, z range."""
        tx, ty = -ay, ax
        ring = [(-half_len, -half_thick), (half_len, -half_thick),
                (half_len, half_thick), (-half_len, half_thick)]
        return [(cx + u * ax + v * tx, cy + u * ay + v * ty, z)
                for z in (zlo, zhi) for u, v in ring]

    def solid(self, pts: Sequence[Tuple[float, float, float]], name: str) -> str:
        """A named box solid: IfcTriangulatedFaceSet (IFC4) or IfcFacetedBrep
        (IFC2X3 has no tessellation), styled with ``name`` -- the resolver's
        part-role vocabulary (wall_i, <tag>_body, <tag>_nameplate ...)."""
        w = self.w
        if self.schema == "IFC4":
            plist = w.add("IFCCARTESIANPOINTLIST3D((" + ",".join(_pt(p) for p in pts) + "))")
            item = w.add(f"IFCTRIANGULATEDFACESET({plist},$,$,{_TRIS},$)")
        else:
            prefs = [w.add(f"IFCCARTESIANPOINT({_pt(p)})") for p in pts]
            faces = []
            for quad in _QUADS:
                loop = w.add("IFCPOLYLOOP((" + ",".join(prefs[i - 1] for i in quad) + "))")
                bound = w.add(f"IFCFACEOUTERBOUND({loop},.T.)")
                faces.append(w.add(f"IFCFACE(({bound}))"))
            shell = w.add(f"IFCCLOSEDSHELL(({','.join(faces)}))")
            item = w.add(f"IFCFACETEDBREP({shell})")
        w.add(f"IFCSTYLEDITEM({item},({self.style}),{_s(name)})")
        return item

    def box(self, name: str, cx: float, cy: float, sx: float, sy: float,
            zlo: float, zhi: float, *, ax: float = 1.0, ay: float = 0.0) -> str:
        """Named box solid ``sx`` long (along ``(ax, ay)``) by ``sy`` across."""
        return self.solid(self.box_pts(cx, cy, ax, ay, sx / 2.0, sy / 2.0, zlo, zhi), name)

    def extrusion(self, xdim: float, ydim: float, depth: float, *, center: Sequence[float]) -> str:
        """IfcExtrudedAreaSolid of a rectangle profile centred at ``center`` in
        the product frame, extruded +Z by ``depth`` (the body kind #152 teaches
        the resolver to read)."""
        w = self.w
        c2 = w.add(f"IFCCARTESIANPOINT({_pt(center)})")
        p2 = w.add(f"IFCAXIS2PLACEMENT2D({c2},$)")
        prof = w.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,'rect',{p2},{_f(xdim)},{_f(ydim)})")
        return w.add(f"IFCEXTRUDEDAREASOLID({prof},{self.a2p0},{self.dirz},{_f(depth)})")

    def shape(self, items: Sequence[str], rep_type: str = "") -> str:
        if not rep_type:
            rep_type = "Tessellation" if self.schema == "IFC4" else "Brep"
        rep = self.w.add(f"IFCSHAPEREPRESENTATION({self.sub},'Body',{_s(rep_type)},({','.join(items)}))")
        return self.w.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({rep}))")

    # -- products + properties -----------------------------------------------
    def product(self, cls: str, name: str, *, plc: str, rep: Optional[str], tag: Optional[str] = None,
                tail: str = "$", object_type: Optional[str] = None) -> str:
        """``cls(GlobalId,OH,Name,Description,ObjectType,Placement,Rep,Tag,<tail>)``
        -- every IfcElement subtype used here has exactly this layout."""
        return self.w.add(
            f"{cls.upper()}({self.gid(cls + ':' + (tag or name))},{self.oh},{_s(name)},$,"
            f"{_s(object_type) if object_type else '$'},{plc},{rep or '$'},{_s(tag) if tag else '$'},{tail})")

    def board(self, tag: str, name: str, plc_parent: str, schedule: Dict[str, Any], *,
              tail: str = ".DISTRIBUTIONBOARD.", object_type: Optional[str] = None, **gear: Any) -> str:
        """The common panel triple: ``gear_items`` solids -> an
        IfcElectricDistributionBoard placed (identity) under ``plc_parent`` ->
        its ``PanelSchedule`` pset.  ``gear`` = the ``gear_items`` keywords."""
        items = self.gear_items(tag, **gear)
        prod = self.product("IfcElectricDistributionBoard", name, plc=self.placement(plc_parent),
                            rep=self.shape(items), tag=tag, tail=tail, object_type=object_type)
        self.pset([prod], "PanelSchedule", schedule)
        return prod

    def pval(self, key: str, val: Any) -> str:
        w = self.w
        if isinstance(val, bool):
            return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCBOOLEAN({'.T.' if val else '.F.'}),$)")
        if isinstance(val, int):
            return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCINTEGER({val}),$)")
        if isinstance(val, Length):
            return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCLENGTHMEASURE({_f(val)}),$)")
        if isinstance(val, float):
            return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCREAL({_f(val)}),$)")
        return w.add(f"IFCPROPERTYSINGLEVALUE({_s(key)},$,IFCLABEL({_s(val)}),$)")

    def pset_def(self, name: str, props: Dict[str, Any], seed: str) -> str:
        refs = [self.pval(k, v) for k, v in props.items()]
        return self.w.add(f"IFCPROPERTYSET({self.gid('pset:' + name + ':' + seed)},{self.oh},"
                          f"{_s(name)},$,({','.join(refs)}))")

    def pset(self, owners: Sequence[str], name: str, props: Dict[str, Any]) -> None:
        seed = ",".join(owners)
        ps = self.pset_def(name, props, seed)
        self.w.add(f"IFCRELDEFINESBYPROPERTIES({self.gid('reldef:' + name + ':' + seed)},{self.oh},"
                   f"$,$,({','.join(owners)}),{ps})")

    def assign_type(self, occurrences: Sequence[str], type_ref: str) -> None:
        self.w.add(f"IFCRELDEFINESBYTYPE({self.gid('reltype:' + type_ref)},{self.oh},$,$,"
                   f"({','.join(occurrences)}),{type_ref})")

    # -- composite parts in the resolver's vocabulary ------------------------
    def room_shell(self, plc_storey: str, *, width: float, depth: float, thick: float,
                   height: float, tail: str = "$") -> str:
        """A room-shell IfcBuildingElementProxy: four ``wall_<i>`` box solids on
        the centerline rectangle ``width`` x ``depth`` (corners overlap by the
        thickness, as rvt.frontdoor.ifc_out writes them) + a RoomInformation
        pset whose clear dimensions are IfcLengthMeasures in file units."""
        name = "Electrical Room"
        hw, hd, ht = width / 2.0, depth / 2.0, thick / 2.0
        runs = [((-hw, -hd), (hw, -hd)), ((hw, -hd), (hw, hd)),
                ((hw, hd), (-hw, hd)), ((-hw, hd), (-hw, -hd))]
        items = []
        for i, (p0, p1) in enumerate(runs, start=1):
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            ln = math.hypot(dx, dy)
            items.append(self.solid(self.box_pts((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0,
                                                 dx / ln, dy / ln, ln / 2.0 + ht, ht, 0.0, height),
                                    f"wall_{i}"))
        rep = self.shape(items)
        plc = self.placement(plc_storey)
        proxy = self.product("IfcBuildingElementProxy", f"{name} room shell", plc=plc, rep=rep, tail=tail)
        self.pset([proxy], "RoomInformation",
                  {"RoomName": name, "ClearWidth": Length(width - thick),
                   "ClearDepth": Length(depth - thick), "ClearHeight": Length(height)})
        return proxy

    def gear_items(self, tag: str, *, cx: float, cy: float, w: float, d: float, zlo: float,
                   zhi: float, front: Tuple[float, float], upright: bool,
                   plate: float = 0.12, proud: float = 0.003) -> List[str]:
        """Body box (``<tag>_enclosure`` for wall gear / ``<tag>_body`` for floor
        gear) centred at (cx, cy) + a thin ``<tag>_nameplate`` proud of the
        front face at 2/3 height (the resolver's front-normal vote)."""
        fx, fy = front
        wx, wy = -fy, fx                                     # width axis
        body = self.solid(self.box_pts(cx, cy, wx, wy, w / 2.0, d / 2.0, zlo, zhi),
                          f"{tag}_{'enclosure' if upright else 'body'}")
        pz = zlo + (zhi - zlo) * 2.0 / 3.0
        plate_item = self.solid(self.box_pts(cx + fx * (d / 2.0 + proud), cy + fy * (d / 2.0 + proud),
                                             wx, wy, plate, proud, pz - plate / 5.0, pz + plate / 5.0),
                                f"{tag}_nameplate")
        return [body, plate_item]

    # -- serialise -------------------------------------------------------------
    def text(self, pins: str) -> str:
        w = self.w
        if self._storeys:
            self.aggregate(self.building, self._storeys)
        for whole, parts in self._aggregated.items():
            w.add(f"IFCRELAGGREGATES({self.gid('agg:' + whole)},{self.oh},$,$,{whole},({','.join(parts)}))")
        for struct, prods in self._contained.items():
            w.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE({self.gid('contains:' + struct)},{self.oh},$,$,"
                  f"({','.join(prods)}),{struct})")
        for bad in ("'", ";", "*/", "DATA"):                   # keep the header comment lexer-safe
            assert bad not in pins, f"{self.name}: pins text must not contain {bad!r}"
        return (
            "ISO-10303-21;\n"
            f"/* {HEADER_MARK}.\n"
            f" * written by {GENERATOR} (fixture {self.name}) -- regenerate, never edit.\n"
            f" * pins: {pins} */\n"
            "HEADER;\n"
            "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n"
            f"FILE_NAME({_s(self.name + '.ifc')},'{_STAMP}',('tekton'),('tekton'),"
            "'tekton conformance fixtures','tekton make_ifc_fixtures','');\n"
            f"FILE_SCHEMA(('{self.schema}'));\n"
            "ENDSEC;\n"
            "DATA;\n"
            + w.body() +
            "ENDSEC;\n"
            "END-ISO-10303-21;\n")


# ---------------------------------------------------------------------------
# THE FIXTURES -- one builder each; (name, pins, notes, parity_xfail)
# ---------------------------------------------------------------------------

Fixture = Dict[str, Any]
FIXTURES: List[Fixture] = []


def fixture(name: str, pins: str, *, notes: Sequence[str] = (),
            parity_xfail: Optional[str] = None) -> Callable[[Callable[[], Model]], Callable[[], Model]]:
    def deco(fn: Callable[[], Model]) -> Callable[[], Model]:
        FIXTURES.append({"name": name, "pins": pins, "notes": list(notes),
                         "parity_xfail": parity_xfail, "build": fn})
        return fn
    return deco


def _room_with_panel(m: Model, *, k: float) -> Model:
    """Shared body of the two unit fixtures: a 6 x 4.5 m room shell + one
    wall-mounted DP-1 on the north wall, authored in the file's unit (``k``
    file units per metre)."""
    sto, plc_sto = m.storey("Level 1", 0.0)
    shell = m.room_shell(plc_sto, width=6.0 * k, depth=4.5 * k, thick=0.2 * k, height=3.0 * k)
    panel = m.board("DP-1", "DP-1 distribution panel 480Y/277 V", plc_sto,
                    {"PanelName": "DP-1", "Voltage": "480Y/277 V", "BusRating": 400.0,
                     "MainsType": "Main breaker", "Mounting": "SURFACE", "NumberOfCircuits": 42},
                    cx=1.0 * k, cy=(2.25 - 0.1 - 0.125) * k, w=0.9 * k, d=0.25 * k, zlo=0.6 * k,
                    zhi=2.0 * k, front=(0.0, -1.0), upright=True, plate=0.12 * k, proud=0.003 * k)
    m.contain(sto, [shell, panel])
    return m


@fixture("a_units_mm",
         "SI millimetre length unit (IfcSIUnit MILLI METRE): scale 0.001, room shell 6 x 4.5 m "
         "read back in metres, one wall panel",
         notes=["length_scale_m_per_unit must be 0.001 and every insertion/wall coordinate metres; "
                "a regression here means the unit scale stopped being applied to tessellated vertices",
                "#153: RoomInformation ClearWidth/Depth/Height are IfcLengthMeasure in mm and come "
                "back UNSCALED today (5800, not 5.8) -- pset length measures are informational and "
                "not unit-converted by the resolver; the census/measure decision belongs to #153"])
def _fx_a() -> Model:
    return _room_with_panel(Model("a_units_mm", unit="milli"), k=1000.0)


@fixture("b_units_feet",
         "IfcConversionBasedUnit FOOT (0.3048 m via IfcMeasureWithUnit): scale 0.3048, same room "
         "as a_units_mm authored in feet",
         notes=["steplite has no schema row for IfcDimensionalExponents / IfcMeasureWithUnit "
                "internals beyond what calculate_unit_scale reads; the scale must still be 0.3048"])
def _fx_b() -> Model:
    return _room_with_panel(Model("b_units_feet", unit="foot"), k=1.0 / 0.3048)


@fixture("c_storeys_relative_placement",
         "two storeys (0 and 4 m) under a building rotated 90 deg and offset (10,5), products "
         "placed by NON-identity local placements with local (not world-baked) vertices",
         notes=["world = site o building o storey o product o local vertex: insertion_m proves the "
                "chain composes (position_source = placement-chain + local geometry)",
                "#331: LP-2 is named a lighting panel but classifies receptacle_panelboard: the "
                "208Y/120 V (ll <= 240) rule fires before the lighting/LP- name rule in "
                "_classify_equipment -- today's order, pinned; #331 decides bug vs intended",
                "#156: level ids/elevations are pinned here; how they map onto the base's levels "
                "at build time is #156's expectation to add"])
def _fx_c() -> Model:
    m = Model("c_storeys_relative_placement", building=((10.0, 5.0, 0.0), (0.0, 1.0, 0.0)))
    s1, p1 = m.storey("Ground", 0.0)
    s2, p2 = m.storey("First", 4.0)
    # floor transformer on Ground: product frame at local (2,1,0) rotated -90 (x -> -y)
    plc_t = m.placement(p1, m.axis((2.0, 1.0, 0.0), x=(0.0, -1.0, 0.0)))
    t_items = m.gear_items("T-1", cx=0.0, cy=0.0, w=0.8, d=0.6, zlo=0.0, zhi=1.1,
                           front=(0.0, -1.0), upright=False)
    t1 = m.product("IfcTransformer", "T-1 dry-type transformer 75 kVA", plc=plc_t,
                   rep=m.shape(t_items), tag="T-1", tail=".VOLTAGE.")
    m.pset([t1], "TransformerSchedule", {"RatingkVA": 75.0, "Primary": "480 V",
                                           "Secondary": "208Y/120 V"})
    # wall panel on First: product frame at local (3, 0.5, 0), enclosure 0.8..2.0 above ITS storey
    plc_p = m.placement(p2, m.axis((3.0, 0.5, 0.0)))
    p_items = m.gear_items("LP-2", cx=0.0, cy=0.0, w=0.6, d=0.2, zlo=0.8, zhi=2.0,
                           front=(1.0, 0.0), upright=True)
    lp2 = m.product("IfcElectricDistributionBoard", "LP-2 lighting panel 208Y/120 V",
                    plc=plc_p, rep=m.shape(p_items), tag="LP-2", tail=".DISTRIBUTIONBOARD.")
    m.pset([lp2], "PanelSchedule", {"PanelName": "LP-2", "Voltage": "208Y/120 V", "BusRating": 100.0,
                                    "MainsType": "Main lugs only", "FedFrom": "T-1"})
    m.contain(s1, [t1])
    m.contain(s2, [lp2])
    return m


@fixture("d_wall_opening_door",
         "IfcWallStandardCase with an IfcExtrudedAreaSolid body, an IfcOpeningElement related by "
         "IfcRelVoidsElement, an IfcDoor filling it (IfcRelFillsElement), plus one tessellated panel",
         notes=["#152 (landed, PR #327): the wall's IfcExtrudedAreaSolid body IS read -- has_body "
                "true, insertion = footprint centre [4,2,0] through the (1,2,0) placement, dims "
                "6.0 x 0.2 x 3.0, position_source placement-chain + local geometry; the extrusion "
                "carries no IfcStyledItem so its item name is null",
                "#157: the wall is still recorded as equipment kind wall / disposition recorded and "
                "room is null; #157 turns it into a WallRun with the opening recorded",
                "#155 (landed): steplite keeps the IfcDoor in its IfcProduct closure exactly as "
                "ifcopenshell does -- D-1 is recorded equipment of kind proxy with its body read "
                "(insertion [3.45,2,0], dims 0.9 x 0.05 x 2.1) and an unmapped family plan; parity "
                "holds, no xfail"])
def _fx_d() -> Model:
    m = Model("d_wall_opening_door")
    sto, plc_sto = m.storey("Level 1", 0.0)
    plc_wall = m.placement(plc_sto, m.axis((1.0, 2.0, 0.0)))
    wall = m.product("IfcWallStandardCase", "Basic Wall 200 mm", plc=plc_wall,
                     rep=m.shape([m.extrusion(6.0, 0.2, 3.0, center=(3.0, 0.0))], "SweptSolid"),
                     tag="W-1", tail=".STANDARD.")
    m.pset([wall], "Pset_WallCommon", {"IsExternal": False, "LoadBearing": False})
    plc_open = m.placement(plc_wall, m.axis((2.0, 0.0, 0.0)))
    opening = m.product("IfcOpeningElement", "Door opening", plc=plc_open,
                        rep=m.shape([m.extrusion(0.9, 0.4, 2.1, center=(0.45, 0.0))], "SweptSolid"),
                        tag="O-1", tail=".OPENING.")
    door = m.product("IfcDoor", "Single flush door 900 x 2100", plc=m.placement(plc_open),
                     rep=m.shape([m.extrusion(0.9, 0.05, 2.1, center=(0.45, 0.0))], "SweptSolid"),
                     tag="D-1", tail="2.1,0.9,.DOOR.,.SINGLE_SWING_LEFT.,$")
    m.w.add(f"IFCRELVOIDSELEMENT({m.gid('voids')},{m.oh},$,$,{wall},{opening})")
    m.w.add(f"IFCRELFILLSELEMENT({m.gid('fills')},{m.oh},$,$,{opening},{door})")
    panel = m.board("DP-1", "DP-1 distribution panel 480Y/277 V", plc_sto,
                    {"PanelName": "DP-1", "Voltage": "480Y/277 V", "BusRating": 400.0},
                    cx=5.0, cy=1.775, w=0.9, d=0.25, zlo=0.6, zhi=2.0, front=(0.0, -1.0), upright=True)
    m.contain(sto, [wall, door, panel])
    return m


@fixture("e_space_in_storey",
         "IfcSpace aggregated into the upper of two storeys, one panel contained in the SPACE "
         "(level resolves through the space to L2), one contained directly in the lower storey",
         notes=["#158: the IfcSpace itself is not an IfcElement, so it appears in neither equipment "
                "nor other_products today; #158 reads it into the intent as a room",
                "the panel inside the space must still get level L2 (containment walked space -> storey)"])
def _fx_e() -> Model:
    m = Model("e_space_in_storey")
    s1, p1 = m.storey("Level 1", 0.0)
    s2, p2 = m.storey("Level 2", 3.5)
    plc_space = m.placement(p2)
    space = m.w.add(f"IFCSPACE({m.gid('space:101')},{m.oh},'101',$,$,{plc_space},$,'Electrical 101',"
                    ".ELEMENT.,.INTERNAL.,$)")
    m.aggregate(s2, [space])
    m.pset([space], "Pset_SpaceCommon", {"Reference": "ELEC", "IsExternal": False})
    rp2 = m.board("RP-2", "RP-2 receptacle panel 208Y/120 V", plc_space,
                  {"PanelName": "RP-2", "Voltage": "208Y/120 V", "BusRating": 225.0},
                  cx=2.0, cy=3.0, w=0.5, d=0.15, zlo=0.9, zhi=1.7, front=(-1.0, 0.0), upright=True)
    lp1 = m.board("LP-1", "LP-1 lighting panel 480Y/277 V", p1,
                  {"PanelName": "LP-1", "Voltage": "480Y/277 V", "BusRating": 100.0,
                   "MainsType": "Main lugs only"},
                  cx=2.0, cy=0.1, w=0.5, d=0.15, zlo=0.9, zhi=1.7, front=(0.0, 1.0), upright=True)
    m.contain(space, [rp2])
    m.contain(s1, [lp1])
    return m


@fixture("f_board_type_psets",
         "IfcElectricDistributionBoard + IfcElectricDistributionBoardType (IfcRelDefinesByType), "
         "PanelSchedule on the occurrence overriding a type-level PanelSchedule, "
         "Pset_ManufacturerTypeInformation on the type, fed from an MSB switchboard in the file",
         notes=["get_psets semantics: type psets first, occurrence values override per name "
                "(Mounting comes out SURFACE from the occurrence, NumberOfCircuits 42 from the type)",
                "the feeder edge MSB -> DP-1 comes from FedFrom; MSB has no catalog line -> house family"])
def _fx_f() -> Model:
    m = Model("f_board_type_psets")
    sto, plc_sto = m.storey("Level 1", 0.0)
    msb_items = m.gear_items("MSB", cx=1.5, cy=3.0, w=2.4, d=0.9, zlo=0.1, zhi=2.4, front=(0.0, -1.0),
                             upright=False)
    msb_items.append(m.box("pad_MSB", 1.5, 3.0, 2.6, 1.1, 0.0, 0.1))
    msb = m.product("IfcElectricDistributionBoard", "MSB main switchboard 2000 A", plc=m.placement(plc_sto),
                    rep=m.shape(msb_items), tag="MSB", tail=".SWITCHBOARD.")
    m.pset([msb], "SwitchboardSchedule", {"PanelName": "MSB", "Voltage": "480Y/277 V", "BusRating": 2000.0,
                                          "MainsType": "Main breaker", "Sections": 3, "FedFrom": "UTILITY"})
    dp = m.board("DP-1", "DP-1", plc_sto,
                 {"PanelName": "DP-1", "Voltage": "480Y/277 V", "BusRating": 400.0,
                  "MainsType": "Main breaker", "Mounting": "SURFACE", "FedFrom": "MSB"},
                 object_type="Distribution panelboard",
                 cx=5.0, cy=3.9, w=0.9, d=0.25, zlo=0.5, zhi=2.0, front=(0.0, -1.0), upright=True)
    type_psets = [m.pset_def("PanelSchedule", {"Mounting": "FLUSH", "NumberOfCircuits": 42}, "type:DP"),
                  m.pset_def("Pset_ManufacturerTypeInformation",
                             {"Manufacturer": "tekton house", "ModelLabel": "THP-400-42"}, "type:DP")]
    dp_type = m.w.add(f"IFCELECTRICDISTRIBUTIONBOARDTYPE({m.gid('type:DP')},{m.oh},'THP 400 A 42 ckt',$,$,"
                      f"({','.join(type_psets)}),$,'THP-400','distribution panelboard',.DISTRIBUTIONBOARD.)")
    m.assign_type([dp], dp_type)
    m.contain(sto, [msb, dp])
    return m


@fixture("g_mep_recorded_kinds",
         "IfcTransformer (floor, TransformerSchedule, fed from an external MSB), IfcCableCarrierSegment "
         "CABLETRAYSEGMENT with a conduit_msb_t1 solid, IfcDiscreteAccessory strut support",
         notes=["kinds transformer / conduit_run / support; the tray and the strut are disposition "
                "recorded (no generated family); the transformer maps to make_transformer",
                "FedFrom MSB with no MSB in the file -> feeder root external, edge kind primary"])
def _fx_g() -> Model:
    m = Model("g_mep_recorded_kinds")
    sto, plc_sto = m.storey("Level 1", 0.0)
    t_items = m.gear_items("T-1", cx=4.0, cy=1.0, w=0.8, d=0.6, zlo=0.1, zhi=1.2, front=(0.0, 1.0),
                           upright=False)
    t_items.append(m.box("pad_T-1", 4.0, 1.0, 1.0, 0.8, 0.0, 0.1))
    t1 = m.product("IfcTransformer", "T-1 dry-type transformer 45 kVA", plc=m.placement(plc_sto),
                   rep=m.shape(t_items), tag="T-1", tail=".VOLTAGE.")
    m.pset([t1], "TransformerSchedule", {"RatingkVA": 45.0, "Primary": "480 V", "Secondary": "208Y/120 V",
                                           "ImpedancePercent": 5.75, "FedFrom": "MSB"})
    tray = m.product("IfcCableCarrierSegment", "Tray MSB to T-1", plc=m.placement(plc_sto),
                     rep=m.shape([m.box("conduit_msb_t1", 2.0, 1.0, 3.2, 0.3, 2.6, 2.7)]),
                     tag="CT-1", tail=".CABLETRAYSEGMENT.")
    strut = m.product("IfcDiscreteAccessory", "Strut ST-1 trapeze", plc=m.placement(plc_sto),
                      rep=m.shape([m.box("strut_channel", 2.0, 1.0, 0.5, 0.041, 2.55, 2.6, ax=0.0, ay=1.0)]),
                      tag="ST-1", tail=".BRACKET.")
    m.pset([strut], "SupportSchedule", {"StrutSize": "P1000", "RodSize": "3/8 in", "AttachTo": "structure"})
    m.contain(sto, [t1, tray, strut])
    return m


@fixture("h_mapped_item_reuse",
         "one IfcRepresentationMap (enclosure + nameplate) reused by three panels through "
         "IfcMappedItem + IfcCartesianTransformationOperator3D (two translated, one rotated 90 deg)",
         notes=["each occurrence must resolve its OWN insertion and front normal from the shared map: "
                "world = placement o target-operator o inverse(map origin) o vertex",
                "#331: the LP-n lighting panels at 208Y/120 V classify receptacle_panelboard (voltage "
                "rule before name rule, as in fixture c) -- today's order, pinned"])
def _fx_h() -> Model:
    m = Model("h_mapped_item_reuse")
    sto, plc_sto = m.storey("Level 1", 0.0)
    items = m.gear_items("panel", cx=0.0, cy=0.0, w=0.6, d=0.2, zlo=0.9, zhi=1.9, front=(0.0, -1.0),
                         upright=True)
    maprep = m.w.add(f"IFCSHAPEREPRESENTATION({m.sub},'Body','Tessellation',({','.join(items)}))")
    rmap = m.w.add(f"IFCREPRESENTATIONMAP({m.a2p0},{maprep})")
    panels = []
    for tag, origin, axis1, axis2 in (("LP-1", (1.0, 4.0, 0.0), None, None),
                                      ("LP-2", (2.5, 4.0, 0.0), None, None),
                                      ("LP-3", (5.0, 2.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))):
        lo = m.w.add(f"IFCCARTESIANPOINT({_pt(origin)})")
        a1 = m.w.add(f"IFCDIRECTION({_pt(axis1)})") if axis1 else "$"
        a2 = m.w.add(f"IFCDIRECTION({_pt(axis2)})") if axis2 else "$"
        op = m.w.add(f"IFCCARTESIANTRANSFORMATIONOPERATOR3D({a1},{a2},{lo},1.,$)")
        mi = m.w.add(f"IFCMAPPEDITEM({rmap},{op})")
        p = m.product("IfcElectricDistributionBoard", f"{tag} lighting panel 208Y/120 V",
                      plc=m.placement(plc_sto), rep=m.shape([mi], "MappedRepresentation"), tag=tag,
                      tail=".DISTRIBUTIONBOARD.")
        m.pset([p], "PanelSchedule", {"PanelName": tag, "Voltage": "208Y/120 V", "BusRating": 100.0,
                                      "MainsType": "Main lugs only"})
        panels.append(p)
    m.contain(sto, panels)
    return m


@fixture("i_schema_ifc2x3",
         "FILE_SCHEMA IFC2X3: IfcFacetedBrep bodies (no tessellation in 2x3), an "
         "IfcBuildingElementProxy room shell with CompositionType, an IfcElectricDistributionPoint panel",
         notes=["#159: schema is reported as IFC2X3; steplite has no IfcElectricDistributionPoint row, "
                "so the 2x3 panel is absent from its IfcProduct closure (equipment empty) while real "
                "ifcopenshell records it as kind proxy -- #159 classifies it as a board",
                "steplite reads the 2x3 proxy's CompositionType slot as PredefinedType (harmless: the "
                "proxy is the room shell)"],
         parity_xfail="#159: IfcElectricDistributionPoint (IFC2X3) dropped by steplite, kept by ifcopenshell")
def _fx_i() -> Model:
    m = Model("i_schema_ifc2x3", schema="IFC2X3")
    sto, plc_sto = m.storey("Level 1", 0.0)
    shell = m.room_shell(plc_sto, width=5.0, depth=4.0, thick=0.2, height=2.8, tail=".ELEMENT.")
    items = m.gear_items("DP-1", cx=1.5, cy=1.775, w=0.9, d=0.25, zlo=0.6, zhi=2.0, front=(0.0, -1.0),
                         upright=True)
    panel = m.product("IfcElectricDistributionPoint", "DP-1 distribution board", plc=m.placement(plc_sto),
                      rep=m.shape(items), tag="DP-1", tail=".DISTRIBUTIONBOARD.,$")
    m.pset([panel], "PanelSchedule", {"PanelName": "DP-1", "Voltage": "480Y/277 V", "BusRating": 400.0})
    m.contain(sto, [shell, panel])
    return m


# ---------------------------------------------------------------------------
# resolver summary (runs INSIDE the --resolve subprocess; imports the engine)
# ---------------------------------------------------------------------------

def _r(v: Any, nd: int = 3) -> Any:
    """Round every number (3 dp, -0.0 normalised) so pins never sit on noise."""
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return v
    if isinstance(v, (int, float)):
        x = round(float(v), nd)
        return x + 0.0 if x != 0 else 0.0
    if isinstance(v, dict):
        return {k: _r(x, nd) for k, x in v.items()}
    return [_r(x, nd) for x in v]


def summarize(path: str) -> Dict[str, Any]:
    """The pinned projection of ``resolve_intent(path)`` -- small, stable, and
    THE one place a sibling issue extends when its DONE pins a new fact
    (#153 census, #157 wall openings, #158 spaces ...): add the key here,
    ``--update-expected``, commit the diff."""
    from rvt.ifc import intent as I         # FIRST: rvt.ifc selects the backend (RVT_STEPLITE_FORCE)
    import ifcopenshell                                        # type: ignore
    backend = "steplite" if getattr(ifcopenshell, "IS_STEPLITE", False) else "ifcopenshell"
    try:
        model = I.resolve_intent(path)
    except Exception as exc:                                   # pinned failure modes are data too
        return {"backend": backend, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    equipment = [{
        "tag": e.tag, "name": e.name, "ifcClass": e.ifc_class, "predefinedType": e.predefined_type,
        "kind": e.kind, "disposition": e.disposition, "level": e.level, "typeName": e.type_name,
        "has_body": e.geometry.has_body, "insertion_m": _r(e.insertion_m),
        "front_normal": _r(e.front_normal), "yaw_deg": _r(e.yaw_deg, 1), "dims_m": _r(e.dims_m),
        "mounting": e.mounting, "position_source": e.position_source, "fed_from": e.fed_from,
        "contract": _r({k: v for k, v in e.contract.items() if not k.startswith("_")}),
        "items": [it.name for it in e.geometry.items],
    } for e in model.equipment]
    room = None
    if model.room is not None:
        room = {"name": model.room.name, "level": model.room.level,
                "walls": [{"id": w.wall_id, "start": _r(w.p0_m), "end": _r(w.p1_m),
                           "thickness": _r(w.thickness_m), "height": _r(w.height_m),
                           "base": _r(w.base_m), "synthesized": w.synthesized,
                           "openings": [{"width": _r(o.width_m), "center_along": _r(o.center_along_m)}
                                        for o in w.openings]}
                          for w in model.room.walls],
                "doors": len(model.room.doors), "info": _r(dict(sorted(model.room.info.items())))}
    return {
        "backend": backend, "ok": True,
        "schema": model.schema, "project": model.project_name,
        "length_scale_m_per_unit": _r(model.length_scale_m, 6),
        "levels": [{k: _r(lv[k]) for k in ("id", "name", "elevation", "elevation_from_placement")}
                   for lv in model.levels],
        "equipment": equipment,
        "other_products": [{k: o.get(k) for k in ("name", "ifcClass", "kind", "disposition")}
                           for o in model.other_products],
        "room": room,
        "feeders": [{"source": ed.source, "target": ed.target, "kind": ed.kind} for ed in model.feeders],
        "conduit_runs": [r.get("item") for r in model.conduit_runs],
        "family_plans": [{"tag": p.tag, "kind": p.kind, "status": p.status, "catalog": p.catalog}
                         for p in model.family_plans],
        "audit": {k: model.audit.get(k) for k in ("feeder_roots_external", "load_equipment_unfed",
                                                 "positions_all_zero")},
    }


def resolve_summaries(paths: Sequence[str], *, force_steplite: bool) -> Dict[str, Dict[str, Any]]:
    """Run ``--resolve`` in a child interpreter and return {path: summary}.
    The child gets ``src/`` on PYTHONPATH; ``force_steplite`` exports
    RVT_STEPLITE_FORCE=1 so the engine puts the bundled shim FIRST -- the
    backend is process-global, so a child is the only robust way to choose it."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(ROOT, "src")] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
    env.pop("RVT_STEPLITE_FORCE", None)
    if force_steplite:
        env["RVT_STEPLITE_FORCE"] = "1"
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--resolve", *paths],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"--resolve failed ({proc.returncode}):\n{proc.stderr[-3000:]}")
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# generation / check / pin
# ---------------------------------------------------------------------------

def render_all() -> Dict[str, str]:
    """{fixture name: full .ifc text} for every registered fixture."""
    out: Dict[str, str] = {}
    for fx in FIXTURES:
        text = fx["build"]().text(fx["pins"])
        assert len(text.encode("ascii")) < MAX_BYTES, f"{fx['name']}: {len(text)} bytes >= {MAX_BYTES}"
        out[fx["name"]] = text
    return out


def _path(name: str, ext: str) -> str:
    return os.path.join(FIXTURE_DIR, name + ext)


def _read(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="ascii", newline="") as fh:
        return fh.read()


def _write_if_changed(path: str, text: str) -> bool:
    if _read(path) == text:
        return False
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(text)
    return True


def header_doc(fx: Fixture) -> Dict[str, Any]:
    """The registry-derived half of ``<name>.expected.json`` (resolver-free)."""
    return {"fixture": fx["name"], "generator": GENERATOR, "pins": fx["pins"], "notes": fx["notes"],
            "parity_xfail": fx["parity_xfail"], "pinned_backend": "steplite"}


def load_expected(name: str) -> Optional[Dict[str, Any]]:
    text = _read(_path(name, ".expected.json"))
    return json.loads(text) if text is not None else None


def _dump(doc: Dict[str, Any]) -> str:
    return json.dumps(doc, indent=1) + "\n"


def check() -> List[str]:
    """Drift report, one line per problem: a committed .ifc that differs from
    the generator or is missing, an .expected.json that is missing or whose
    registry-derived header (pins / notes / parity_xfail) is stale, and any
    stray file the generator does not produce."""
    problems: List[str] = []
    rendered = render_all()
    for fx in FIXTURES:
        name = fx["name"]
        got = _read(_path(name, ".ifc"))
        if got is None:
            problems.append(f"missing: {name}.ifc (run {GENERATOR})")
        elif got != rendered[name]:
            problems.append(f"drift: {name}.ifc differs from the generator (run {GENERATOR})")
        doc = load_expected(name)
        if doc is None:
            problems.append(f"missing: {name}.expected.json (run {GENERATOR} --update-expected)")
        elif {k: v for k, v in doc.items() if k != "expected"} != header_doc(fx):
            problems.append(f"drift: {name}.expected.json header is stale vs the registry (run {GENERATOR})")
    for fn in sorted(os.listdir(FIXTURE_DIR)) if os.path.isdir(FIXTURE_DIR) else ():
        stem = fn[:-len(".expected.json")] if fn.endswith(".expected.json") else os.path.splitext(fn)[0]
        if stem not in rendered:
            problems.append(f"stray: {fn} is not produced by the generator")
    return problems


def write_fixtures() -> List[str]:
    """(Re)write every .ifc and refresh each .expected.json HEADER from the
    registry (the resolver-derived ``expected`` body is left untouched)."""
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    written = []
    for name, text in render_all().items():
        if _write_if_changed(_path(name, ".ifc"), text):
            written.append(name + ".ifc")
    for fx in FIXTURES:
        doc = load_expected(fx["name"])
        if doc is not None and _write_if_changed(_path(fx["name"], ".expected.json"),
                                                 _dump({**header_doc(fx), "expected": doc["expected"]})):
            written.append(fx["name"] + ".expected.json (header)")
    return written


def update_expected() -> List[str]:
    """Re-pin every .expected.json from TODAY's steplite resolver.  A
    deliberate act: the diff it produces is the expectation change a PR owns."""
    write_fixtures()
    paths = [_path(fx["name"], ".ifc") for fx in FIXTURES]
    summaries = resolve_summaries(paths, force_steplite=True)
    changed = []
    for fx, path in zip(FIXTURES, paths):
        summary = summaries[path]
        assert summary.pop("backend") == "steplite", "RVT_STEPLITE_FORCE did not select the shim"
        if _write_if_changed(_path(fx["name"], ".expected.json"), _dump({**header_doc(fx), "expected": summary})):
            changed.append(fx["name"])
    return changed


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="report drift vs the committed fixtures; exit 1 on any")
    g.add_argument("--update-expected", action="store_true",
                   help="re-pin the .expected.json files from today's steplite resolver")
    g.add_argument("--list", action="store_true", help="print the fixture table")
    g.add_argument("--resolve", nargs="+", metavar="IFC", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.resolve:
        json.dump({p: summarize(p) for p in a.resolve}, sys.stdout, indent=1)
        return 0
    if a.list:
        texts = render_all()
        for fx in FIXTURES:
            print(f"{fx['name']:32s} {len(texts[fx['name']]):6d} B  {fx['pins']}")
        return 0
    if a.check:
        problems = check()
        for p in problems:
            print(p)
        print(f"{'DRIFT' if problems else 'ok'}: {len(FIXTURES)} fixtures checked against {GENERATOR}")
        return 1 if problems else 0
    if a.update_expected:
        changed = update_expected()
        print(f"expected: {len(changed)} re-pinned {changed}" if changed else "expected: unchanged")
        return 0
    written = write_fixtures()
    print(f"fixtures: {len(written)} written {written}" if written else "fixtures: unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""#714 -- a carried IFC pset parameter DRIVES the part it describes.

#769 carried an IFC's property sets onto the family as typed parameters, as values
only.  ``rvt.ifc.pset_drive`` matches each carried LENGTH to ``(part, axis)`` -- the
pset's own product, one span of that part, equal to float noise, never guessed -- and
the assembly lane wires it: x / y by the in-plane drive law (``drive_law``, planes at
the part's own faces, symmetric only when the part is centred), z by the #787 Case B
height law.  Everything else is a value with a stated reason.  A refused drive is
dropped whole (``settle_drives``): the file is the build that never asked for it.

The fixture is OURS, generated here (no owner file): a transformer-shaped assembly of
four tessellated boxes in a millimetre IFC, psets attached per product -- the table
#714 names (BodyWidth / BodyDepth / BodyHeight on the tank shell, PadWidth / PadDepth
on the pad, FrontClearance / TopClearance on the clearance volumes) plus a mismatch, a
shared pset and a text property.

Nothing here claims a family flexes in Revit: no pset drive has a desktop verdict
(hard rule 4) and no route calls the result editable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
from contextlib import ExitStack

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.ifc import pset_drive as PD

needs_schema = pytest.mark.skipif(not HAVE_SCHEMA, reason="class schema cache absent")

# the route enters the write-side release context (2025 target) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the native
    codec singletons (by design); do that once before the guard's first snapshot."""
    if not HAVE_SCHEMA:
        return
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t714rw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- fixture

_HDR = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('{name}','2026-01-01T00:00:00',('t'),('t'),'tekton-test','tekton-test','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'t',$,$,$,$,$);
#2=IFCORGANIZATION($,'t',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton-test','TT');
#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,0);
#6=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#10=IFCUNITASSIGNMENT((#6));
#11=IFCDIRECTION((0.,0.,1.));
#12=IFCDIRECTION((1.,0.,0.));
#13=IFCCARTESIANPOINT((0.,0.,0.));
#14=IFCAXIS2PLACEMENT3D(#13,#11,#12);
#15=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#14,$);
#16=IFCPROJECT('0project0000000000000t',#5,'T',$,$,$,$,(#15),#10);
#17=IFCLOCALPLACEMENT($,#14);
"""
_TRIS = ("((1,3,2),(1,4,3),(5,6,7),(5,7,8),(1,2,6),(1,6,5),(2,3,7),(2,7,6),"
         "(3,4,8),(3,8,7),(4,1,5),(4,5,8))")


def ifc_text(products, psets, name="xfmr714.ifc") -> str:
    """A millimetre IFC4 of axis-aligned tessellated boxes ``[(name, lo_xyz,
    hi_xyz)]`` with psets ``[(pset, [product names], [(prop, IFC type, value)])]``."""
    out = [_HDR.format(name=name)]
    nid, ids = 100, {}
    for pn, (x0, y0, z0), (x1, y1, z1) in products:
        pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
               (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        pl = ",".join("(" + ",".join(repr(float(c)) for c in p) + ")" for p in pts)
        out += [f"#{nid}=IFCCARTESIANPOINTLIST3D(({pl}));",
                f"#{nid + 1}=IFCTRIANGULATEDFACESET(#{nid},$,.T.,{_TRIS},$);",
                f"#{nid + 2}=IFCSHAPEREPRESENTATION(#15,'Body','Tessellation',(#{nid + 1}));",
                f"#{nid + 3}=IFCPRODUCTDEFINITIONSHAPE($,$,(#{nid + 2}));",
                f"#{nid + 4}=IFCBUILDINGELEMENTPROXY('{nid + 4:022d}',#5,'{pn}',$,$,#17,"
                f"#{nid + 3},$,.NOTDEFINED.);"]
        ids[pn] = nid + 4
        nid += 10
    for psn, on, props in psets:
        pids = []
        for prop, t, v in props:
            val = f"'{v}'" if isinstance(v, str) else repr(float(v))
            out.append(f"#{nid}=IFCPROPERTYSINGLEVALUE('{prop}',$,{t}({val}),$);")
            pids.append(nid)
            nid += 1
        out.append(f"#{nid}=IFCPROPERTYSET('{nid:022d}',#5,'{psn}',$,"
                   f"({','.join('#%d' % i for i in pids)}));")
        out.append(f"#{nid + 1}=IFCRELDEFINESBYPROPERTIES('{nid + 1:022d}',#5,$,$,"
                   f"({','.join('#%d' % ids[o] for o in on)}),#{nid});")
        nid += 2
    out.append("ENDSEC;\nEND-ISO-10303-21;\n")
    return "\n".join(out)


PRODUCTS = [
    ("pad_slab", (-1000, -900, 0), (1000, 900, 150)),
    ("tank_shell", (-787.4, -600, 150), (787.4, 400, 1650)),
    ("clearance_front_volume", (-787.4, -4000, 0), (787.4, -900, 1980)),
    ("clearance_top_volume", (-787.4, -600, 1650), (787.4, 400, 2564.4)),
]
_L = "IFCLENGTHMEASURE"
PSETS = [
    ("Pset_Pad", ["pad_slab"], [("PadWidth", _L, 2000), ("PadDepth", _L, 1800)]),
    ("Pset_Body", ["tank_shell"], [("BodyWidth", _L, 1574.8), ("BodyDepth", _L, 1000),
                                   ("BodyHeight", _L, 1500), ("BodyLength", _L, 1600)]),
    ("Pset_TransformerClearances", ["clearance_front_volume"], [("FrontClearance", _L, 3100)]),
    ("Pset_TopClear", ["clearance_top_volume"], [("TopClearance", _L, 914.4)]),
    ("Pset_Shared", ["tank_shell", "pad_slab"], [("SharedSpan", _L, 1000),
                                                 ("InsulationClass", "IFCLABEL", "ONAN")]),
]
#: parameter -> (part, axis) the plan must drive; everything else is a value
EXPECTED = {
    "PadWidth": ("pad_slab", "x"), "PadDepth": ("pad_slab", "y"),
    "BodyWidth": ("tank_shell", "x"), "BodyDepth": ("tank_shell", "y"),
    "BodyHeight": ("tank_shell", "z"),
    "FrontClearance": ("clearance_front_volume", "y"),
    "TopClearance": ("clearance_top_volume", "z"),
}
VALUE_ONLY = {"BodyLength": "equal to none", "SharedSpan": "2 products",
              "InsulationClass": "text parameter"}


def _ifc(d, products=PRODUCTS, psets=PSETS, name="xfmr714.ifc") -> str:
    p = os.path.join(str(d), name)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(ifc_text(products, psets, name=name))
    return p


def _measured(path):
    from rvt.ifc import assembly_parts as AP
    from rvt.ifc import pset_params as PP
    return AP.read_assembly(path).to_parts(), PP.collect(path)


def _sha_file(path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t714sha_")
    try:
        path = os.path.join(d, "f.rfa")
        rep = prod.write(path)
        assert (rep.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, rep
        return _sha_file(path)
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- the plan (pure)

def _box(name, w, d, h, *, c=(0.0, 0.0), base=0.0):
    return {"name": name, "shape": "box", "width_ft": w, "depth_ft": d, "height_ft": h,
            "center": list(c), "base_z_ft": base}


def _coll(**params):
    """``name=(product(s), value_ft)`` -> a ``pset_params.collect`` shape."""
    out = {"params": {}, "sources": {}, "skipped": [], "notes": []}
    for n, (on, v) in params.items():
        ons = [on] if isinstance(on, str) else list(on)
        out["params"][n] = ("length", v)
        out["sources"][n] = {"pset": "P", "product": ", ".join(ons), "products": ons,
                             "tier": "given"}
    return out


def _rows(plan):
    return {r["parameter"]: r for r in plan["rows"]}


def test_the_fixture_plan_matches_the_issue_table(tmp_path):
    pytest.importorskip("numpy")
    parts, coll = _measured(_ifc(tmp_path))
    plan = PD.plan(parts, coll)
    rows = _rows(plan)
    assert sorted(rows) == sorted(list(EXPECTED) + list(VALUE_ONLY))
    for n, (part, ax) in EXPECTED.items():
        assert (rows[n]["status"], rows[n]["part"], rows[n]["axis"]) == (PD.DRIVES, part, ax), rows[n]
    for n, why in VALUE_ONLY.items():
        assert rows[n]["status"] == PD.VALUE_ONLY and why in rows[n]["reason"], rows[n]
    # x drives of the centred parts are symmetric; the off-centre y drives are not
    sym = {d["caption"]: bool(d.get("symmetric")) for d in plan["drives"]}
    assert sym == {"PadWidth": True, "BodyWidth": True, "PadDepth": False,
                   "BodyDepth": False, "FrontClearance": False}
    # the planes are the part's OWN faces, not origin-centred
    by = {p["name"]: p for p in parts}
    for d in plan["drives"]:
        p = by[next(iter(d["parts"]))]
        k = 0 if d["axis"] == "x" else 1
        half = (p["width_ft"] if k == 0 else p["depth_ft"]) / 2.0
        assert (d["lo"], d["hi"]) == pytest.approx((p["center"][k] - half, p["center"][k] + half))
    # z: both parts sit off the origin elevation, so each holds its base by a
    # locked unlabelled height and labels its own span
    caps = [(h["caption"], h.get("locked", False), h["group"]) for h in plan["heights"]]
    assert caps == [(None, True, "BodyHeight"), ("BodyHeight", False, "BodyHeight"),
                    (None, True, "TopClearance"), ("TopClearance", False, "TopClearance")]


def test_the_plan_is_deterministic_and_order_free(tmp_path):
    pytest.importorskip("numpy")
    parts, coll = _measured(_ifc(tmp_path))
    a = PD.plan(parts, coll)
    rev = copy.deepcopy(coll)
    rev["params"] = dict(reversed(list(rev["params"].items())))
    assert PD.plan(parts, rev) == a == PD.plan(parts, copy.deepcopy(coll))


@pytest.mark.parametrize("part, params, status, why", [
    # equal to two spans: the name's axis word decides, or nothing does
    (_box("sq", 2.0, 2.0, 1.0), {"Side": ("sq", 2.0)}, PD.VALUE_ONLY, "not guessed"),
    (_box("sq", 2.0, 2.0, 1.0), {"SqDepth": ("sq", 2.0)}, PD.DRIVES, "axis word picked y"),
    # a hair off: reported, never snapped; far off: the spans are named
    (_box("b", 2.0, 1.0, 1.0), {"BW": ("b", 2.0 + 1.0 / 128 / 12)}, PD.VALUE_ONLY, "never snapped"),
    (_box("b", 2.0, 1.0, 1.0), {"BW": ("b", 3.0)}, PD.VALUE_ONLY, "equal to none"),
    # whose part: none, several products, a decomposed product, two parts of one name
    (_box("b", 2.0, 1.0, 1.0), {"BW": ([], 2.0)}, PD.VALUE_ONLY, "no named product"),
    (_box("b", 2.0, 1.0, 1.0), {"BW": (["b", "c"], 2.0)}, PD.VALUE_ONLY, "2 products"),
    (_box("b [1/2]", 2.0, 1.0, 1.0), {"BW": ("b", 2.0)}, PD.VALUE_ONLY, "measured into 1 solid(s)"),
    (_box("other", 2.0, 1.0, 1.0), {"BW": ("b", 2.0)}, PD.VALUE_ONLY, "not a measured part"),
    # a lying cylinder's sketch is not what Revit draws; a polygon has z only
    ({"name": "r", "shape": "cylinder_x", "radius_ft": 0.5, "length_ft": 2.0,
      "height_ft": 1.0}, {"L": ("r", 2.0)}, PD.VALUE_ONLY, "lying cylinder"),
    ({"name": "g", "shape": "polygon", "vertices": [[0, 0], [2, 0], [1, 1]],
      "height_ft": 1.5}, {"GW": ("g", 2.0)}, PD.VALUE_ONLY, "equal to none"),
    ({"name": "g", "shape": "polygon", "vertices": [[0, 0], [2, 0], [1, 1]],
      "height_ft": 1.5}, {"GH": ("g", 1.5)}, PD.DRIVES, "z span"),
])
def test_every_unmatched_parameter_says_why(part, params, status, why):
    rows = _rows(PD.plan([part], _coll(**params)))
    (r,) = rows.values()
    assert r["status"] == status and why in r["reason"], r


def test_two_parts_of_one_name_and_one_span_claimed_twice_are_values():
    two = PD.plan([_box("b", 2.0, 1.0, 1.0), _box("b", 2.0, 1.0, 1.0, c=(3.0, 0.0))],
                  _coll(BW=("b", 2.0)))
    assert "2 measured parts" in two["rows"][0]["reason"] and not two["drives"]
    twice = _rows(PD.plan([_box("b", 2.0, 1.0, 1.0)], _coll(AW=("b", 2.0), BW=("b", 2.0))))
    assert twice["AW"]["status"] == PD.DRIVES
    assert twice["BW"]["status"] == PD.VALUE_ONLY and "already driven by AW" in twice["BW"]["reason"]


def test_a_part_on_the_origin_elevation_needs_no_held_base():
    plan = PD.plan([_box("b", 2.0, 1.0, 1.5)], _coll(BH=("b", 1.5)))
    assert plan["heights"] == [{"caption": "BH", "lo": 0.0, "hi": 1.5, "group": "BH",
                                "parts": {"b": {"start": "lo", "end": "hi"}}}]


def test_settle_rows_never_reports_an_unauthored_chain():
    rows = [{"parameter": "A", "status": PD.DRIVES, "part": "p", "axis": "x", "reason": "r"},
            {"parameter": "B", "status": PD.DRIVES, "part": "p", "axis": "z", "reason": "r"},
            {"parameter": "C", "status": PD.VALUE_ONLY, "part": "", "axis": "", "reason": "t"}]
    out = {r["parameter"]: r for r in PD.settle_rows(
        rows, {"wired": ["A"], "refused": {"B": "height drive for 'B' not wired (X)"}})}
    assert out["A"]["status"] == PD.DRIVES
    assert out["B"]["status"] == PD.VALUE_ONLY and "factory refused" in out["B"]["reason"]
    assert out["C"] == rows[2]
    lines = PD.summarise(list(out.values()))
    assert "1 of 3" in lines[0] and "NO desktop-Revit verdict" in lines[0]
    assert not any("is editable" in t or "flexes" in t for t in lines)


# --------------------------------------------------------------------------- the factory

def _build(parts, coll, **kw):
    from rvt.famgen import factory as F
    plan = PD.plan(parts, coll)
    prod = F.make_generic_model(parts=parts, name="X714", numeric_params=dict(coll["params"]),
                                drives=plan["drives"], heights=plan["heights"],
                                settle_drives=True, **kw)
    return plan, prod


@needs_schema
def test_each_driven_axis_carries_one_dimension_labelled_by_its_parameter(tmp_path):
    pytest.importorskip("numpy")
    from rvt.famgen import constraint_law as CL
    from rvt.famgen import drive_law as DL
    parts, coll = _measured(_ifc(tmp_path))
    _plan, prod = _build(parts, coll)
    doc = prod.doc
    assert prod.drive_settle == {"wired": sorted(EXPECTED), "refused": {}}
    labels = {}
    for d in doc.by_class("LinearDimString"):
        for seg in d.obj["m_ArrSegInfo"]:
            labels.setdefault(int(seg.get("m_paramId", -1)), []).append(d)
    for n in EXPECTED:
        assert len(labels.get(doc.params[n].elem_id, [])) == 1, n
    for n in VALUE_ONLY:
        if n in doc.params:
            assert doc.params[n].elem_id not in labels, n
    # 5 in-plane drives x 2 edges; 2 heights x 2 cap faces
    assert len(DL._sketch_locks(doc)) == 10
    assert prod.heights["face_locks"] == 4 and prod.heights["locked_unlabelled"] == 2
    assert doc.born_drive_law is True and CL.check_doc(doc) == []
    # the type row keeps the GIVEN values, untouched by the drive
    rows = doc.types[doc.current_type][1]
    for n in EXPECTED:
        assert rows[doc.params[n].elem_id] == coll["params"][n][1]


@needs_schema
def test_the_settled_build_is_deterministic(tmp_path):
    pytest.importorskip("numpy")
    parts, coll = _measured(_ifc(tmp_path))
    assert _sha(_build(parts, coll)[1]) == _sha(_build(parts, coll)[1])


@needs_schema
@pytest.mark.parametrize("victim, how", [
    ("BodyWidth", "symmetric"),          # the base drive wires, its EQ does not
    ("BodyDepth", "inplane"),            # the drive itself refuses
    ("BodyHeight", "height"),            # the held base wires, the labelled height does not
])
def test_a_refused_group_is_dropped_whole_and_the_bytes_say_so(tmp_path, monkeypatch, victim, how):
    pytest.importorskip("numpy")
    from rvt.famgen import drive_law as DL
    from rvt.famgen import factory as F
    from rvt.famgen import height_law as HL
    parts, coll = _measured(_ifc(tmp_path))
    plan = PD.plan(parts, coll)
    if how == "symmetric":
        real = DL.wire_symmetric

        def fake(doc, base, axis="x"):
            if base.get("caption") == victim:
                raise ValueError("probe: no EQ")
            return real(doc, base, axis)
        monkeypatch.setattr(DL, "wire_symmetric", fake)
    elif how == "inplane":
        real = DL.wire_linear_drive

        def fake(doc, **kw):
            if kw.get("caption") == victim:
                raise ValueError("probe: refused")
            return real(doc, **kw)
        monkeypatch.setattr(DL, "wire_linear_drive", fake)
    else:
        real = HL.wire_height_drive

        def fake(doc, **kw):
            if kw.get("caption") == victim:
                raise ValueError("probe: refused")
            return real(doc, **kw)
        monkeypatch.setattr(HL, "wire_height_drive", fake)
    _p, prod = _build(parts, coll)
    assert sorted(prod.drive_settle["refused"]) == [victim]
    assert "probe" in prod.drive_settle["refused"][victim]
    assert victim not in prod.drive_settle["wired"]
    # the file is the build that never asked for the victim's group
    without = F.make_generic_model(
        parts=parts, name="X714", numeric_params=dict(coll["params"]),
        drives=[d for d in plan["drives"] if d["group"] != victim],
        heights=[h for h in plan["heights"] if h["group"] != victim])
    assert _sha(prod) == _sha(without)
    rows = {r["parameter"]: r for r in PD.settle_rows(plan["rows"], prod.drive_settle)}
    assert rows[victim]["status"] == PD.VALUE_ONLY and "factory refused" in rows[victim]["reason"]


@needs_schema
def test_every_group_refused_is_the_build_without_drives(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    from rvt.famgen import drive_law as DL
    from rvt.famgen import factory as F
    from rvt.famgen import height_law as HL

    def no(*a, **k):
        raise ValueError("probe: everything refused")
    monkeypatch.setattr(DL, "wire_linear_drive", no)
    monkeypatch.setattr(HL, "wire_height_drive", no)
    parts, coll = _measured(_ifc(tmp_path))
    _p, prod = _build(parts, coll)
    assert prod.drive_settle["wired"] == [] and sorted(prod.drive_settle["refused"]) == sorted(EXPECTED)
    base = F.make_generic_model(parts=parts, name="X714", numeric_params=dict(coll["params"]))
    assert _sha(prod) == _sha(base)


# --------------------------------------------------------------------------- the route

def _plane(o):
    s = o["m_pSurface"]["value"]
    x, y = s["m_xVec"], s["m_yVec"]
    n = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    m = sum(c * c for c in n) ** 0.5
    return s["m_origin"], tuple(c / m for c in n)


def _locks_on_planes(path):
    """(sketch locks, off their plane, face locks, off their plane) read back from
    the WRITTEN file under its own release (the 913 read-back, per lock)."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        E = {eid: (fi.class_name(r.class_id), fi.decode(0, eid, 102).value)
             for eid, r in fi.unit_records(0).get(102, {}).items()
             if fi.class_name(r.class_id) in ("RefPlane", "Alignment", "CurveElem",
                                              "ExtrusionElem", "SketchPlane", "VarSketch")}
    sk_n = sk_off = f_n = f_off = 0
    for _eid, (cls, v) in E.items():
        if cls != "Alignment":
            continue
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in v["m_witnessRefs"]]
        kind = lambda x: E.get(x["m_elemId"], ("",))[0]                  # noqa: E731
        pl = [x for x in g if kind(x) == "RefPlane"]
        cu = [x for x in g if kind(x) == "CurveElem"]
        ex = [x for x in g if kind(x) == "ExtrusionElem"]
        if len(pl) != 1:
            continue
        p0, nrm = _plane(E[pl[0]["m_elemId"]][1])
        if len(cu) == 1:
            c = E[cu[0]["m_elemId"]][1]["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
            pts = [[c["m_origin"][i] + c["m_dirVec"][i] * t for i in range(3)]
                   for t in c["m_endParams"]]
            sk_n += 1
            sk_off += any(abs(sum((p[i] - p0[i]) * nrm[i] for i in range(3))) > 1e-6
                          for p in pts)
        elif len(ex) == 1:
            o = E[ex[0]["m_elemId"]][1]
            pv = {int(p["m_paramId"]): float(p["m_value"])
                  for p in o["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
            off = pv[-1001801 if ex[0]["m_geomTag"] == 0 else -1001800]
            helper = next(c["value"] for c in o["m_cellList"]["value"]["m_cells"]
                          if c["ptr_class"] == "ExtrusionElemExtrusionHelper")
            trf = E[E[helper["m_sketchId"]][1]["m_sketchPlaneId"]][1]["m_oTrf"]["value"]
            sn = [trf["m_3x3"][i][2] for i in range(3)]
            face = [trf["m_or"][i] + sn[i] * off for i in range(3)]
            f_n += 1
            f_off += abs(sum((face[i] - p0[i]) * nrm[i] for i in range(3))) > 1e-6
    return sk_n, sk_off, f_n, f_off


def _route(ifc, out, **opts):
    from rvt.frontdoor import router as R
    return R.route({"ifc": ifc}, "rfa", out=str(out), quiet=True, **opts)


@needs_schema
@pytest.mark.parametrize("year", [None, 2025, 2024])
def test_the_route_wires_and_reports_every_matched_parameter(tmp_path, year):
    pytest.importorskip("numpy")
    from rvt.famgen import constraint_law as CL
    res = _route(_ifc(tmp_path), tmp_path / "o",
                 **({"target_version": year} if year else {}))
    assert res.ok, res.status
    if year:                             # built AT that release, not a native fallback
        assert (res.target_version or {}).get("status") == "match", res.target_version
    rfa = res.files["rfa"]
    rep = json.load(open(res.files["rfa_report"], encoding="utf-8"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    assert CL.check_file(rfa) == []
    sk_n, sk_off, f_n, f_off = _locks_on_planes(rfa)
    assert (sk_n, sk_off, f_off) == (10, 0, 0) and f_n >= 4
    side = json.load(open(res.files["pset_drives"], encoding="utf-8"))
    rows = {r["parameter"]: r for r in side["rows"]}
    assert {n for n, r in rows.items() if r["status"] == PD.DRIVES} == set(EXPECTED)
    for n, why in VALUE_ONLY.items():
        assert why in rows[n]["reason"]
    head = [c for c in res.caveats if c.startswith("YOUR PSET PARAMETERS AS DRIVES")]
    assert head and "7 of 10" in head[0] and "NO desktop-Revit verdict" in head[0]
    for n, (part, ax) in EXPECTED.items():
        assert any(c.startswith(f"{n} DRIVES {part} along {ax}") for c in res.caveats), n
    for n in VALUE_ONLY:
        assert any(c.startswith(f"{n} is a value only:") for c in res.caveats), n
    # nothing is called editable: the only mention is the disclaimer
    assert not any("editable" in c and "nothing here is called editable" not in c
                   and "not editable" not in c.lower() for c in res.caveats
                   if "#714" in c or " DRIVES " in c or "value only" in c)


@needs_schema
def test_the_route_is_deterministic(tmp_path):
    pytest.importorskip("numpy")
    ifc = _ifc(tmp_path)
    a = _route(ifc, tmp_path / "a").files["rfa"]
    b = _route(ifc, tmp_path / "b").files["rfa"]
    assert _sha_file(a) == _sha_file(b)


@needs_schema
def test_a_refused_drive_on_the_route_is_reported_as_a_value(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    from rvt.famgen import height_law as HL
    real = HL.wire_height_drive

    def fake(doc, **kw):
        if kw.get("caption") == "TopClearance":
            raise ValueError("probe: refused")
        return real(doc, **kw)
    monkeypatch.setattr(HL, "wire_height_drive", fake)
    res = _route(_ifc(tmp_path), tmp_path / "o")
    assert res.ok, res.status
    rows = {r["parameter"]: r for r in
            json.load(open(res.files["pset_drives"], encoding="utf-8"))["rows"]}
    assert rows["TopClearance"]["status"] == PD.VALUE_ONLY
    assert "factory refused" in rows["TopClearance"]["reason"]
    assert any(c.startswith("TopClearance is a value only:") for c in res.caveats)
    assert any("6 of 10" in c for c in res.caveats)


def test_an_ifc_without_a_drivable_pset_reaches_the_builder_unchanged(tmp_path, monkeypatch):
    # pins the WIRE (the byte half is measured in the record): no matched
    # parameter -> no drive keys at all, so the build is the pre-#714 one
    pytest.importorskip("numpy")
    from rvt.frontdoor import router as R
    seen = []

    def fake_famspec_rfa(res, kind, kw, out_dir, sub, **k):
        seen.append(dict(kw))
        res.files["rfa"] = "captured"
    monkeypatch.setattr(R, "_famspec_rfa", fake_famspec_rfa)
    for i, psets in enumerate(([], [("P", ["tank_shell"], [("InsulationClass", "IFCLABEL", "ONAN")])],
                               [("P", ["tank_shell"], [("BodyLength", _L, 1600)])])):
        res = R.RouteResult(ok=True, status="", route="ifc->rfa")
        R._assembly_rfa(res, _ifc(tmp_path, psets=psets, name=f"n{i}.ifc"), str(tmp_path), {})
    assert len(seen) == 3
    for kw in seen:
        assert not ({"drives", "heights", "settle_drives"} & set(kw)), sorted(kw)
    res = R.RouteResult(ok=True, status="", route="ifc->rfa")
    R._assembly_rfa(res, _ifc(tmp_path), str(tmp_path), {})
    assert seen[-1]["settle_drives"] is True and len(seen[-1]["drives"]) == 5


# --------------------------------------------------------------------------- #967 review

def _legs(d, legs_psets, name):
    products = PRODUCTS + [("leg_1", (-900, -800, -700), (-800, -700, 0)),
                           ("leg_2", (800, 700, -700), (900, 800, 0))]
    return _measured(_ifc(d, products=products, psets=PSETS + legs_psets, name=name))


@pytest.mark.parametrize("v2", [700, 650], ids=["equal", "different"])
def test_one_label_on_two_products_names_no_part(tmp_path, v2):
    """A per-occurrence pset (each leg its own Pset_Leg) is normal exporter
    output: the label is recorded against BOTH products and stays a value --
    never the first leg driven alone and the second dropped unsaid."""
    from rvt.ifc import pset_drive as PD
    parts, coll = _legs(tmp_path, [("Pset_Leg", ["leg_1"], [("LegHeight", _L, 700)]),
                                   ("Pset_Leg", ["leg_2"], [("LegHeight", _L, v2)])],
                        f"legs_{v2}.ifc")
    assert sorted(coll["sources"]["LegHeight"]["products"]) == ["leg_1", "leg_2"]
    row = _rows(PD.plan(parts, coll))["LegHeight"]
    assert row["status"] == PD.VALUE_ONLY and "2 products" in row["reason"], row


def test_an_unnamed_second_owner_is_still_an_owner(tmp_path):
    from rvt.ifc import pset_drive as PD
    products = PRODUCTS + [("", (2000, 2000, 0), (2100, 2100, 100))]
    psets = PSETS + [("Pset_Odd", ["", "tank_shell"], [("OddWidth", _L, 1574.8)])]
    parts, coll = _measured(_ifc(tmp_path, products=products, psets=psets, name="odd.ifc"))
    row = _rows(PD.plan(parts, coll))["OddWidth"]
    assert row["status"] == PD.VALUE_ONLY and "unnamed" in row["reason"], row


def test_a_name_whose_axis_word_contradicts_the_one_matching_span_is_a_value(tmp_path):
    """BodyWidth = 1000 mm equals only tank_shell's y span: the name says x,
    so it is not guessed (#967 review)."""
    from rvt.ifc import pset_drive as PD
    psets = [p for p in PSETS if p[0] != "Pset_Body"] + [
        ("Pset_Body", ["tank_shell"], [("BodyWidth", _L, 1000)])]
    parts, coll = _measured(_ifc(tmp_path, psets=psets, name="contra.ifc"))
    row = _rows(PD.plan(parts, coll))["BodyWidth"]
    assert row["status"] == PD.VALUE_ONLY and "name says x" in row["reason"], row

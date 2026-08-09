"""tests for rvt.ifc.steplite -- the stdlib-only IFC read path (perf-deps
stream).

PROOF OBLIGATIONS (the stream's DONE bar):

1. PARSER EQUIVALENCE -- attribute-for-attribute equality against the real
   ifcopenshell on BOTH reference IFCs (every entity, every named attribute,
   psets, unit scale, local placements, by_type ordering, get_inverse).
2. PIPELINE BYTE-EQUALITY -- ``rvt.ifc.intent.resolve_intent`` ->
   ``intent_to_json`` and ``rvt.ifc.product_facts`` -> facts record produce
   BYTE-IDENTICAL JSON whether ifcopenshell or the steplite shim serves the
   reads (subprocess pair; the shim side runs with ``RVT_STEPLITE_FORCE=1``).
3. STDLIB-ONLY -- steplite parses and serves a real product with numpy and
   ifcopenshell both unimportable (``python -S`` + empty path).
4. SELECTION -- the shim stands down to a real ifcopenshell when one is
   importable (never shadows), and ``tekton_env.ensure_engine`` appends the
   shim exactly when the real library is absent.

ifcopenshell-dependent tests skip cleanly when it is not installed (the
plugin sandboxes); the stdlib-only tests always run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SHIM = os.path.join(SRC, "rvt", "ifc", "_ifcos_shim")
ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")
LIGHT_IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")

ifcopenshell = pytest.importorskip if False else None  # (per-test skips below)

try:
    import ifcopenshell as _ifcos          # noqa: F401
    import ifcopenshell.util.element as _ue
    import ifcopenshell.util.placement as _up
    import ifcopenshell.util.unit as _uu
    HAVE_IFCOS = not getattr(_ifcos, "IS_STEPLITE", False)
except ImportError:                        # pragma: no cover - sandbox path
    HAVE_IFCOS = False

try:
    import numpy as _np                    # noqa: F401
    HAVE_NUMPY = True
except ImportError:                        # pragma: no cover
    HAVE_NUMPY = False

from rvt.ifc import steplite as SL

needs_corpus = pytest.mark.skipif(
    not (os.path.isfile(ROOM_IFC) and os.path.isfile(LIGHT_IFC)),
    reason="reference IFCs absent")
needs_ifcos = pytest.mark.skipif(not HAVE_IFCOS, reason="ifcopenshell not installed")


# ===========================================================================
# 1. parser equivalence against the real library
# ===========================================================================

def _canon(x):
    """Canonical form for cross-library value comparison."""
    if HAVE_IFCOS and isinstance(x, _ifcos.entity_instance):
        try:
            sid = x.id()
        except Exception:                  # pragma: no cover
            sid = 0
        if sid:
            return ("E", sid)
        return ("T", x.is_a(), x.wrappedValue)
    if isinstance(x, SL.Entity):
        return ("E", x.id())
    if isinstance(x, SL.TypedValue):
        return ("T", x.is_a(), x.wrappedValue)
    if isinstance(x, (list, tuple)):
        return tuple(_canon(i) for i in x)
    return x


def _assert_attrs_equivalent(fr, fs) -> int:
    """Every entity of the real-library file ``fr``: same class and every
    named attribute equal (canonicalised) in the steplite file ``fs``.
    Returns the number of attributes compared."""
    assert fs.schema == fr.schema
    n = 0
    for er in fr:
        es = fs.by_id(er.id())
        assert es.is_a() == er.is_a(), er.id()
        for k, v in er.get_info(recursive=False).items():
            if k in ("id", "type"):
                continue
            assert _canon(getattr(es, k)) == _canon(v), (er.id(), er.is_a(), k)
            n += 1
    return n


def _assert_by_type_equivalent(fr, fs, classes) -> None:
    """by_type subtype closure AND ordering match for every class name."""
    for cls in classes:
        assert [e.id() for e in fr.by_type(cls)] == [e.id() for e in fs.by_type(cls)], cls


@needs_ifcos
@needs_corpus
@pytest.mark.parametrize("path", [ROOM_IFC, LIGHT_IFC],
                         ids=["electrical-room", "downlight"])
def test_every_entity_every_attribute_matches_ifcopenshell(path):
    assert _assert_attrs_equivalent(_ifcos.open(path), SL.open(path)) > 400


@needs_ifcos
@needs_corpus
@pytest.mark.parametrize("path", [ROOM_IFC, LIGHT_IFC],
                         ids=["electrical-room", "downlight"])
def test_by_type_ordering_and_closure_match(path):
    _assert_by_type_equivalent(_ifcos.open(path), SL.open(path), (
        "IfcProduct", "IfcElement", "IfcObject", "IfcStyledItem",
        "IfcBuildingStorey", "IfcProject", "IfcApplication",
        "IfcLightFixture", "IfcOpeningElement", "IfcTessellatedFaceSet",
        "IfcElectricDistributionBoard", "IfcSpatialElement"))


@needs_ifcos
@needs_corpus
def test_psets_unit_scale_placement_inverse_match():
    for path in (ROOM_IFC, LIGHT_IFC):
        fr = _ifcos.open(path)
        fs = SL.open(path)
        for er in fr.by_type("IfcObject"):
            es = fs.by_id(er.id())
            assert _ue.get_psets(er) == SL.get_psets(es), er.id()
        assert _uu.calculate_unit_scale(fr) == SL.calculate_unit_scale(fs)
        for er in fr.by_type("IfcElement"):
            es = fs.by_id(er.id())
            assert _up.get_local_placement(er.ObjectPlacement).tolist() == \
                   SL.get_local_placement(es.ObjectPlacement), er.id()
        for er in fr.by_type("IfcTriangulatedFaceSet")[:8]:
            es = fs.by_id(er.id())
            assert sorted(x.id() for x in fr.get_inverse(er)) == \
                   [x.id() for x in fs.get_inverse(es)], er.id()
        # get_type on every typed occurrence
        for er in fr.by_type("IfcElectricDistributionBoard"):
            tr = _ue.get_type(er)
            ts = SL.get_type(fs.by_id(er.id()))
            assert (tr.id() if tr else None) == (ts.id() if ts else None)


# ===========================================================================
# 2. pipeline byte-equality (real ifcopenshell vs forced steplite shim)
# ===========================================================================

_PIPELINE = """\
import json, sys
import ifcopenshell
from rvt.ifc import intent as I
from rvt.ifc import product_facts as PF
backend = "steplite" if getattr(ifcopenshell, "IS_STEPLITE", False) else "real"
model = I.resolve_intent(sys.argv[1])
intent = I.intent_to_json(model)
facts = PF.extract_product_facts(sys.argv[2])
rec = PF.to_facts_record(facts)
out = {"backend": backend, "intent": intent,
       "facts_record": rec, "facts_full": facts.to_json(),
       "validate_problems": PF.validate_record(rec)}
json.dump(out, open(sys.argv[3], "w"), indent=1, default=str)
"""


def _run_pipeline(tmp_path, tag, env_extra):
    out = os.path.join(str(tmp_path), f"{tag}.json")
    script = os.path.join(str(tmp_path), "pipeline.py")
    with open(script, "w") as fh:
        fh.write(_PIPELINE)
    env = dict(os.environ)
    env.pop("RVT_STEPLITE_FORCE", None)
    env.update(env_extra)
    proc = subprocess.run([sys.executable, script, ROOM_IFC, LIGHT_IFC, out],
                          cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with open(out) as fh:
        return fh.read()


@needs_ifcos
@needs_corpus
@pytest.mark.skipif(not HAVE_NUMPY, reason="intent path needs numpy")
def test_intent_and_facts_json_byte_equal_across_backends(tmp_path):
    real = _run_pipeline(tmp_path, "real", {"PYTHONPATH": SRC})
    lite = _run_pipeline(tmp_path, "lite",
                         {"PYTHONPATH": os.pathsep.join([SRC, SHIM]),
                          "RVT_STEPLITE_FORCE": "1"})
    jr, jl = json.loads(real), json.loads(lite)
    assert jr["backend"] == "real" and jl["backend"] == "steplite"
    assert jr["validate_problems"] == [] and jl["validate_problems"] == []
    # byte equality of everything downstream of the parser
    jr.pop("backend")
    jl.pop("backend")
    assert json.dumps(jr, sort_keys=False) == json.dumps(jl, sort_keys=False)


# ===========================================================================
# 3. stdlib-only guarantees
# ===========================================================================

@needs_corpus
def test_steplite_runs_without_numpy_or_ifcopenshell():
    """steplite + the product-facts route on a bare interpreter: ``-S``
    (no site-packages) proves zero third-party imports are reachable."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {SRC!r})\n"
        f"sys.path.insert(1, {SHIM!r})\n"
        "import os; os.environ['RVT_STEPLITE_FORCE'] = '1'\n"
        "import ifcopenshell\n"
        "assert getattr(ifcopenshell, 'IS_STEPLITE', False), 'expected the shim'\n"
        "from rvt.ifc import product_facts as PF\n"
        f"facts = PF.extract_product_facts({LIGHT_IFC!r})\n"
        "assert facts.counts['meshes'] == 29, facts.counts\n"
        "assert facts.product['tag'] == 'CP-6-LED'\n"
        "assert 'ChicagoPlenumSpecification' in facts.psets\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('numpy', 'olefile')]\n"
        "assert not bad, bad\n"
        "print('OK stdlib-only')\n"
    )
    proc = subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT,
                          capture_output=True, text=True, timeout=120,
                          env={k: v for k, v in os.environ.items()
                               if k not in ("PYTHONPATH", "RVT_STEPLITE_FORCE")})
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK stdlib-only" in proc.stdout


@needs_corpus
def test_parser_primitives():
    f = SL.open(LIGHT_IFC)
    # header
    assert f.schema == "IFC4"
    assert f.header.originating_system == "three-d-stage"
    # by_guid round trip + miss behaviour (real library raises too)
    fix = f.by_type("IfcLightFixture")[0]
    assert f.by_guid(fix.GlobalId).id() == fix.id()
    with pytest.raises(RuntimeError):
        f.by_guid("0000000000000000000000")
    # enums / booleans / typed values
    styled = f.by_type("IfcStyledItem")
    assert styled and isinstance(styled[0].Name, str)
    unit = [u for u in f.by_type("IfcProject")[0].UnitsInContext.Units
            if u.UnitType == "LENGTHUNIT"]
    assert unit and unit[0].Name == "METRE" and unit[0].Prefix is None
    val = None
    for pn, props in SL.get_psets(fix).items():
        if "Rating" in props:
            val = props["Rating"]
    assert isinstance(val, str) and val            # IfcLabel -> str
    # inheritance-aware is_a
    tfs = f.by_type("IfcTriangulatedFaceSet")[0]
    assert tfs.is_a("IfcTessellatedFaceSet") and tfs.is_a("ifctessellateditem")
    assert not tfs.is_a("IfcPolygonalFaceSet")
    # derived slots read as None; missing attrs raise AttributeError
    assert tfs.PnIndex is None
    with pytest.raises(AttributeError):
        tfs.NoSuchAttribute                        # noqa: B018
    # unknown-class safety: attribute table absence is a clear error
    ent = SL.Entity(f, 999999, "IFCNOTINSUBSET", ())
    assert ent.is_a() == "IfcNotinsubset"
    with pytest.raises(AttributeError):
        ent.Name                                   # noqa: B018


def test_string_decoding_edge_cases(tmp_path):
    step = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION((''),'2;1');\n"
        "FILE_NAME('x','t',(''),(''),'pp','orig','');\n"
        "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
        "#1=IFCORGANIZATION($,'It''s \\X2\\00E9\\X0\\; ok','a;b',$,$);\n"
        "#2=IFCCARTESIANPOINT((1.5E-1,-2.,+3.25));\n"
        "ENDSEC;\nEND-ISO-10303-21;\n"
    )
    p = os.path.join(str(tmp_path), "t.ifc")
    with open(p, "w") as fh:
        fh.write(step)
    f = SL.open(p)
    org = f.by_id(1)
    assert org.Name == "It's é; ok"           # '' + \X2\ + ';' in string
    assert org.Description == "a;b"
    assert f.by_id(2).Coordinates == (0.15, -2.0, 3.25)
    assert f.header.originating_system == "orig"


# ===========================================================================
# 4. selection: fallback engages only when the real library is absent
# ===========================================================================

@needs_ifcos
def test_shim_stands_down_to_real_ifcopenshell():
    """Shim dir FIRST on the path + real library installed -> the import
    must resolve to the REAL ifcopenshell (deferral, never shadowing)."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, {SHIM!r})\n"
        f"sys.path.insert(1, {SRC!r})\n"
        "import ifcopenshell\n"
        "assert not getattr(ifcopenshell, 'IS_STEPLITE', False), 'shim shadowed the real lib'\n"
        "import ifcopenshell.util.element  # real submodules resolve\n"
        "print('OK stand-down', ifcopenshell.version)\n"
    )
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "RVT_STEPLITE_FORCE")}
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                          capture_output=True, text=True, timeout=120, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK stand-down" in proc.stdout


def test_ensure_engine_appends_shim_only_when_real_absent():
    """Bare interpreter (-S, no site-packages): ensure_engine must append the
    bundled shim and the IFC read route must work end to end -- the plugin's
    zero-install path.  Skips when the synced plugin tree is absent."""
    plugin = os.path.join(ROOT, "plugin")
    shim_pkg = os.path.join(plugin, "lib", "src", "rvt", "ifc", "_ifcos_shim",
                            "ifcopenshell", "__init__.py")
    light = os.path.join(plugin, "skills", "tekton-author", "examples",
                         "chicago-plenum-downlight.ifc")
    if not (os.path.isfile(shim_pkg) and os.path.isfile(light)):
        pytest.skip("plugin tree not synced with the steplite shim + example IFC")
    code = (
        "import sys\n"
        f"sys.path.insert(0, {os.path.join(plugin, 'skills', '_shared')!r})\n"
        "import tekton_env\n"
        f"src = tekton_env.ensure_engine({plugin!r})\n"
        "import ifcopenshell\n"
        "assert getattr(ifcopenshell, 'IS_STEPLITE', False), 'expected the shim on a bare interpreter'\n"
        "from rvt.ifc import product_facts as PF\n"
        f"facts = PF.extract_product_facts({light!r})\n"
        "assert facts.counts['meshes'] == 29\n"
        "print('OK ensure_engine fallback')\n"
    )
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "RVT_STEPLITE_FORCE")}
    proc = subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT,
                          capture_output=True, text=True, timeout=120, env=env)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK ensure_engine fallback" in proc.stdout


# ===========================================================================
# 5. swept solids: IfcExtrudedAreaSolid + profiles + planar curves (#152)
#    -- hand-authored fixture + shared checks (tests/fixtures_ifc_extrusion.py),
#    so the stdlib reader is held to the SAME world numbers as the real library
# ===========================================================================

import fixtures_ifc_extrusion as FX  # noqa: E402  (tests/ is on sys.path under pytest)


@pytest.fixture(scope="module")
def extrusion_path(tmp_path_factory):
    return FX.write_fixture(str(tmp_path_factory.mktemp("extrusion")))


def test_swept_solid_schema_rows_serve_the_read_surface(extrusion_path):
    """The new _SCHEMA rows: attribute access root..leaf, is_a closure,
    by_type subtype closure, typed Segments, type objects for typeName."""
    f = SL.open(extrusion_path)
    solids = f.by_type("IfcExtrudedAreaSolid")
    assert len(solids) == 9
    assert [e.id() for e in f.by_type("IfcSweptAreaSolid")] == [e.id() for e in solids]
    assert [e.id() for e in f.by_type("IfcSolidModel")] == [e.id() for e in solids]
    slab = f.by_id(46)
    assert slab.is_a("IfcSweptAreaSolid") and slab.is_a() == "IfcExtrudedAreaSolid"
    assert slab.Depth == 0.15 and slab.ExtrudedDirection.DirectionRatios == (0.0, 0.0, 1.0)
    assert slab.Position.Location.Coordinates == (0.0, 0.0, -0.15)
    prof = slab.SweptArea
    assert prof.is_a("IfcParameterizedProfileDef") and prof.is_a("IfcProfileDef")
    assert (prof.ProfileType, prof.XDim, prof.YDim) == ("AREA", 6.0, 4.0)
    assert prof.Position.is_a("IfcAxis2Placement2D")
    assert prof.Position.Location.Coordinates == (3.0, 2.0) and prof.Position.RefDirection is None
    assert f.by_id(63).Position is None                    # OPTIONAL solid Position
    # profiles: 5 rectangles + 3 arbitrary closed + 1 circle, subtype closure
    kinds = sorted(p.is_a() for p in f.by_type("IfcProfileDef"))
    assert kinds.count("IfcRectangleProfileDef") == 5
    assert kinds.count("IfcArbitraryClosedProfileDef") == 3
    assert kinds.count("IfcCircleProfileDef") == 1 and f.by_id(150).Radius == 0.15
    # planar curves
    poly = f.by_id(55).OuterCurve
    assert poly.is_a("IfcPolyline") and poly.is_a("IfcCurve") and len(poly.Points) == 5
    ipc = f.by_id(71)
    assert ipc.is_a("IfcIndexedPolyCurve") and ipc.SelfIntersect is False
    assert ipc.Points.is_a("IfcCartesianPointList2D") and len(ipc.Points.CoordList) == 4
    assert [s.is_a() for s in ipc.Segments] == ["IfcLineIndex"] * 4
    assert not ipc.Segments[0].is_a("IfcArcIndex")
    assert [s.wrappedValue for s in ipc.Segments] == [(1, 2), (2, 3), (3, 4), (4, 1)]
    assert f.by_id(61).Segments is None
    assert [c.is_a() for c in f.by_type("IfcCurve")] == ["IfcIndexedPolyCurve"] * 2 + ["IfcPolyline"]
    # styled-item inverse on a solid; the type objects behind typeName
    assert [si.Name for si in f.get_inverse(slab) if si.is_a("IfcStyledItem")] == ["floor_slab"]
    assert SL.get_type(f.by_id(158)).Name == "Bollard 300 dia"          # IfcDiscreteAccessoryType
    assert SL.get_type(f.by_id(97)).PredefinedType == "USERDEFINED"     # IfcBuildingElementProxyType
    assert [t.Name for t in f.by_type("IfcBuildingElementType")] == \
        ["Room shell type", "Generic 150 slab", "Generic 200 wall"]
    assert f.by_id(135).RepresentationMaps[0].MappedRepresentation.Items[0].id() == 131


@pytest.mark.skipif(not HAVE_NUMPY, reason="intent geometry needs numpy")
def test_steplite_entities_drive_the_intent_extrusion_reader(extrusion_path):
    """In-process: steplite entities fed straight to rvt.ifc.intent's
    product analysis land on the fixture's expected WORLD boxes -- the same
    check the real-library test runs."""
    from rvt.ifc import intent as I

    FX.check_world_boxes(FX.geom_by_name(I, SL.open(extrusion_path)))


@pytest.mark.skipif(not HAVE_NUMPY, reason="intent path needs numpy")
def test_extrusion_intent_resolves_on_the_forced_shim(extrusion_path, tmp_path):
    """No-ifcopenshell path (the plugin sandbox / CI): the shim FORCED first,
    resolve_intent reads every extruded body -> 4 walls closing the ring,
    all equipment with geometry and dims, world z + level annotation."""
    out = os.path.join(str(tmp_path), "intent.json")
    code = (
        "import json, sys\n"
        "import ifcopenshell\n"
        "assert getattr(ifcopenshell, 'IS_STEPLITE', False), 'expected the shim'\n"
        "from rvt.ifc import intent as I\n"
        f"m = I.resolve_intent({extrusion_path!r}, plan_families_flag=False)\n"
        f"json.dump(I.intent_to_json(m), open({out!r}, 'w'), indent=1)\n"
        "print('OK shim intent')\n"
    )
    env = dict(os.environ)
    env.update({"PYTHONPATH": os.pathsep.join([SHIM, SRC]), "RVT_STEPLITE_FORCE": "1"})
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK shim intent" in proc.stdout
    with open(out) as fh:
        FX.check_intent_json(json.load(fh))


@needs_ifcos
def test_extrusion_fixture_matches_ifcopenshell(extrusion_path):
    """Parser equivalence for the swept-solid subset (and the type-object
    rows) against the real library on the hand-authored fixture."""
    fr = _ifcos.open(extrusion_path)
    fs = SL.open(extrusion_path)
    assert _assert_attrs_equivalent(fr, fs) > 300
    _assert_by_type_equivalent(fr, fs, (
        "IfcProfileDef", "IfcParameterizedProfileDef", "IfcSweptAreaSolid",
        "IfcSolidModel", "IfcCurve", "IfcBoundedCurve", "IfcRepresentationItem",
        "IfcTypeObject", "IfcElementType", "IfcProduct", "IfcStyledItem"))
    for er in fr.by_type("IfcExtrudedAreaSolid"):
        es = fs.by_id(er.id())
        assert sorted(x.id() for x in fr.get_inverse(er)) == [x.id() for x in fs.get_inverse(es)]
    for er in fr.by_type("IfcElement"):
        es = fs.by_id(er.id())
        assert _up.get_local_placement(er.ObjectPlacement).tolist() == \
               SL.get_local_placement(es.ObjectPlacement), er.id()
        assert _ue.get_psets(er) == SL.get_psets(es), er.id()
        tr, ts = _ue.get_type(er), SL.get_type(es)
        assert (tr.id() if tr else None) == (ts.id() if ts else None), er.id()

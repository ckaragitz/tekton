"""tests/test_genesis_settings.py -- the DOCUMENT-SETTINGS SINGLETON + built-in
style CATALOG constructors (rvt.genesis.settings / rvt.genesis.catalog) --
the K5/K6-FAIL branch of the reader bisection.

Tiers:
  1. structural: every constructor round-trips clean AND byte-exact through
     the archive codec; the whole standard constellation has NO dangling
     references; no constructor reads the sample corpus (except the
     documented enum derivation).
  2. parametric REPRODUCTION of Autodesk's own specimens (feed a specimen's
     parameter values back in -> the object equals the specimen) -- the
     proof each field layout is exact, not guessed.  Skips if the
     extracted corpus is absent.
  3. the built-in category enum + catalog: 1,074 categories / 333 cuttable
     (a format constant identical across samples), 1,407 rows generated, 0
     value-identical to the quarantined Autodesk table.
  4. the ADocument registry population over a decoded document object.
  5. the S-ladder deliverables (probes.json + S*.rvt validate 0 errors) when
     built.
"""
from __future__ import annotations

import json
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import settings as S                                # noqa: E402
from rvt.genesis import catalog as C                                 # noqa: E402
from rvt.genesis.types import IdSource, INVALID, LINEPATTERN_SOLID    # noqa: E402

CACHE = os.environ.get("RVT_SEG_CACHE")
_have_corpus = os.path.isdir(os.path.join(ROOT, "extracted", "rstbasicsampleproject"))
SINGLETONS_DIR = os.path.join(ROOT, "experiments", "genesis", "singletons")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _diff(a, b, path="", out=None):
    """Structural diff tolerant of float repr (round 6)."""
    out = [] if out is None else out
    norm = lambda v: round(v, 6) if isinstance(v, float) else v   # noqa: E731
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out.append((path + "." + k, k in a, k in b))
            else:
                _diff(a[k], b[k], path + "." + k, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif norm(a) != norm(b):
        out.append((path, a, b))
    return out


@pytest.fixture(scope="module")
def rst():
    if not _have_corpus:
        pytest.skip("rst corpus not extracted")
    from rvt.mutate import Document
    return Document.load("rstbasicsampleproject", CACHE)


@pytest.fixture(scope="module")
def rme():
    if not _have_corpus:
        pytest.skip("rme corpus not extracted")
    from rvt.mutate import Document
    return Document.load("rmebasicsampleproject", CACHE)


@pytest.fixture(scope="module")
def constellation():
    return S.standard_settings(IdSource(700_000), tier="all",
                               doc_ids={"units": 690_001, "document_sun": 690_002,
                                        "phase_new": 690_003, "phase_filter": 690_004,
                                        "geo_location": 690_005, "level1": 690_006,
                                        "phase_set": 690_007})


# ---------------------------------------------------------------------------
# tier 1: structural (no corpus)
# ---------------------------------------------------------------------------

def test_constellation_roundtrips_clean_and_byte_exact(constellation):
    rt = constellation.roundtrip()
    assert rt["records"] >= 90
    assert rt["ok"] == rt["records"], rt["failures"][:2]


def test_constellation_has_no_dangling_references(constellation):
    known = [690_001, 690_002, 690_003, 690_004, 690_005, 690_006, 690_007]
    assert constellation.check_references(known_ids=known) == []


def test_constellation_covers_the_named_charter_classes(constellation):
    classes = set(constellation.by_class())
    for must in ("PenWidthTableElem", "BrowserOrganization",
                 "RbsDbViewSystemNavigator", "StructSettingsElem",
                 "WallJoinDefaultSetting", "AutoJoinTracker", "KeynoteTable",
                 "KeynotingSystem", "InitialViewSettings", "RbsWireSettingsElem",
                 "RbsPipeSettingsElem", "RbsDuctSettingsElem", "RbsDuctSizesElem",
                 "ConduitSettingsElem", "CableTraySettingsElem", "DBViewType",
                 "ReconcileBrowserSettingsElem", "ConstructionSetProject"):
        assert must in classes, must


def test_every_registry_class_is_known():
    # every class the constellation emits has a registry disposition
    cat = S.standard_settings(IdSource(1), tier="all", doc_ids={})
    missing = sorted(c for c in cat.by_class() if c not in S.ADOC_REGISTRY
                     and c not in ("Viewer", "Viewport", "DBDrawing"))
    assert missing == [], missing


def test_tiers_are_cumulative():
    n_pen = len(S.standard_settings(IdSource(1), tier="pen", doc_ids={}).records)
    n_bro = len(S.standard_settings(IdSource(1), tier="browser", doc_ids={}).records)
    n_nam = len(S.standard_settings(IdSource(1), tier="named", doc_ids={}).records)
    n_mep = len(S.standard_settings(IdSource(1), tier="mep", doc_ids={}).records)
    n_all = len(S.standard_settings(IdSource(1), tier="all", doc_ids={}).records)
    assert 1 == n_pen < n_bro < n_nam < n_mep < n_all


def test_pen_table_definition():
    rec = S.pen_width_table(elem_id=2)
    t = rec.obj["m_pPenWidthTable"]["value"]
    assert len(t["m_modelPenInfo"]) == len(S.PEN_SCALE_BREAKPOINTS)
    for p in t["m_modelPenInfo"]:
        assert len(p["m_pens"]) == S.PEN_COUNT
    assert t["m_perspectiveModelPenInfo"]["m_invertedScale"] == -1
    assert t["m_draftPenInfo"]["m_invertedScale"] == -1
    # our widths are ISO-128-based mm converted to feet, ascending, capped
    mm_vals = [round(x * 304.8, 4) for x in t["m_perspectiveModelPenInfo"]["m_pens"]]
    assert mm_vals[:9] == pytest.approx([0.13, 0.18, 0.25, 0.35, 0.50, 0.70,
                                          1.00, 1.40, 2.00], abs=1e-4)
    assert all(a <= b for a, b in zip(mm_vals, mm_vals[1:]))
    # coarser scales shift finer (our rule)
    coarse = t["m_modelPenInfo"][-1]["m_pens"]
    fine = t["m_modelPenInfo"][0]["m_pens"]
    assert coarse[3] <= fine[3]
    with pytest.raises(ValueError):
        S.pen_series_mm(0, base=[0.1] * 5)


def test_our_pen_widths_differ_from_the_autodesk_default_series():
    theirs = [0.18, 0.25, 0.35, 0.7, 1.0, 1.4, 2.0, 2.8, 4.0, 5.0, 6.0,
              7.0, 8.0, 9.0, 9.0, 9.0]
    assert S.PEN_WIDTHS_MM != theirs
    same_idx = sum(1 for a, b in zip(S.PEN_WIDTHS_MM, theirs) if abs(a - b) < 1e-9)
    assert same_idx <= 3          # only ISO-series coincidences, not the vector


def test_browser_organization_and_defaults():
    r = S.browser_organization("all", org_type=S.BROWSER_ORG_VIEWS,
                               folders=[S.BIP_VIEW_FAMILY_AND_TYPE],
                               sort_by=S.BIP_VIEW_NAME, is_default=True, elem_id=5)
    assert r.obj["m_type"] == 0 and r.obj["m_bDefault"] is True
    assert r.obj["m_folderDefinitions"][0]["m_parameter"]["m_paramIdPath"] == [S.BIP_VIEW_FAMILY_AND_TYPE]
    assert r.obj["m_sortParameter"]["m_paramIdPath"] == [S.BIP_VIEW_NAME]
    # a project-parameter (positive id) folder joins the deletion set
    r2 = S.browser_organization("X", folders=[142459], elem_id=6,
                                filters=[{"param": 586533, "value": "S", "relation": 1}])
    dele = r2.header["m_parents"]["value"]["m_deletion"]
    assert 142459 in dele and 586533 in dele
    assert r2.obj["m_filters"][0]["m_value"]["m_storageType"] == 3
    orgs = S.default_browser_organizations(IdSource(10))
    assert len(orgs) == 6
    types = sorted(o.obj["m_type"] for o in orgs if o.obj["m_bDefault"])
    assert types == [0, 1, 3, 4]           # one default per tree
    assert all(o.obj["m_symbolInfo"]["value"]["m_name"] == "all"
               for o in orgs if o.obj["m_bDefault"])


def test_system_navigator_constellation_shape():
    recs = S.system_navigator(IdSource(100), phase_id=90, sun_settings_id=91,
                              all_phases_id=92, units_id=93,
                              workset_visibility_id=94, mep_system_tracker_id=95)
    classes = [r.class_name for r in recs]
    assert classes == ["RbsDbViewSystemNavigator", "Viewer", "Viewport", "DBDrawing"]
    view, viewer, viewport, drawing = recs
    assert view.obj["m_viewName"] == "???"
    assert view.obj["m_viewerId"] == viewer.elem_id
    assert view.obj["m_dbDrawingId"] == drawing.elem_id
    assert drawing.obj["m_viewports"] == [viewport.elem_id]
    assert viewport.obj["m_dbViewId"] == view.elem_id
    assert view.obj["m_pParamValueSetInt"] is None
    par = view.header["m_parents"]["value"]
    assert par["m_regenOnly"] == [92, 93, 94]
    assert par["m_deferredParents"] == [95]
    assert viewport.header["m_parents"]["value"]["m_regenOnly"] == [viewer.elem_id]
    for r in recs:
        assert r.roundtrip()["ok"], r.class_name


def test_keynote_table_tree_building():
    entries = [("A", "", "Div A"), ("A1", "A", "child 1"), ("A2", "A", "child 2"),
               ("Z9", "Q", "orphan (parent absent)")]
    r = S.keynote_table(elem_id=7, entries=entries)
    t = r.obj["m_oKeyBasedTreeEntries"]["value"]
    keys = [e["m_key"] for e in t["m_keyBasedTreeEntrySet"]]
    assert keys == ["A", "A1", "A2", "Z9"]
    a = t["m_keyBasedTreeEntrySet"][0]["m_oEntry"]["value"]
    assert [c["m_str"] for c in a["m_childrenKeys"]] == ["A1", "A2"]
    orph = [o["m_str"] for o in t["m_orphans"]]
    assert "A" in orph and "Z9" in orph              # top-level + missing-parent
    empty = S.keynote_table(elem_id=8)
    assert empty.obj["m_name"] == "Standard" and empty.obj["m_isBuiltIn"] is True
    assert empty.obj["m_oKeyBasedTreeEntries"]["value"]["m_keyBasedTreeEntrySet"] == []
    assert empty.roundtrip()["ok"]


def test_struct_settings_uses_our_values_not_metric_template():
    r = S.struct_settings(elem_id=9)
    # ours: 3/32" symbolic cutback, 1'-0" analytical snap, bc families -1
    assert r.obj["m_symbolicCutback"] == pytest.approx(3.0 / 32 / 12)
    assert r.obj["m_analyticalModelSnapDistance"] == pytest.approx(1.0)
    for f in ("m_bcFixedFamilyId", "m_bcPinnedFamilyId", "m_bcRollerFamilyId",
              "m_bcUserFamilyId"):
        assert r.obj[f] == -1
    assert r.roundtrip()["ok"]


def test_regen_wildcards_are_per_class_constants():
    aj = S.auto_join_tracker(elem_id=10)
    wc = [x["m_ref"]["classref"] for x in
          aj.header["m_parents"]["value"]["m_regenWildcards"]]
    assert wc == ["CeilingAndFloor", "FamilyInstance", "Element"]
    wj = S.wall_join_default_setting(elem_id=11)
    assert [x["m_ref"]["classref"] for x in
            wj.header["m_parents"]["value"]["m_regenWildcards"]] == ["BasicWallType"]
    plain = S.initial_view_settings(elem_id=12)
    assert plain.header["m_parents"]["value"]["m_regenWildcards"] == []


def test_mep_tracker_constellation_wiring():
    recs = S.mep_tracker_constellation(IdSource(200), duct_settings_id=190,
                                       pipe_settings_id=191)
    by = {r.class_name: r for r in recs}
    sysro = by["MEPSystemTracker"].header["m_parents"]["value"]["m_regenOnly"]
    assert set(sysro) == {190, 191, by["MEPComponentTracker"].elem_id,
                          by["LayoutNodesTracker"].elem_id}
    nd = by["MEPNetworkDataElem"].header["m_parents"]["value"]["m_regenOnly"]
    assert nd == [by["MEPNetworkTracker"].elem_id]
    for r in recs:
        assert r.roundtrip()["ok"], r.class_name


def test_wire_sizes_from_house_table_shape():
    r = S.wire_sizes_from_house_table({"Copper": 301, "Aluminum": 302},
                                      {"75": 311, "90": 312},
                                      {"THWN-2": 321, "THHN": 322}, elem_id=300)
    mats = {m["first"]: m["second"] for m in r.obj["m_mapMaterials"]}
    assert set(mats) == {301, 302}
    tr = {t["first"]: t["second"] for t in mats[301]["m_mapTemperatureRatings"]}
    assert set(tr) == {311, 312}
    sizes = tr[311]["m_arrWireSizes"]
    assert sizes[0]["m_strSize"] == "14" and sizes[0]["m_dAmpacity"] == 20.0   # NEC 310.16 Cu 75C
    assert 321 in tr[311]["m_setInsulationIds"]
    # correction factors stored in Kelvin
    cf = {c["first"]: c["second"] for c in mats[301]["m_mapCorrectionFactors"]}
    assert cf[311]["m_arrFactors"][0]["m_dMin"] == pytest.approx(294.15)
    dele = r.header["m_parents"]["value"]["m_deletion"]
    for i in (301, 302, 311, 312, 321, 322):
        assert i in dele
    assert r.roundtrip()["ok"]


def test_duct_sizes_and_settings_defaults():
    ds = S.duct_sizes(elem_id=400)
    shapes = {p["first"]: len(p["second"]["m_sizeData"]) for p in ds.obj["m_shapeSizes"]}
    assert set(shapes) == {0, 1, 2} and all(n > 10 for n in shapes.values())
    row = ds.obj["m_shapeSizes"][2]["second"]["m_sizeData"][0]
    assert row["m_dInnerDiameter"] == 12.0 and row["m_dOuterDiameter"] == 12.0
    st = S.duct_settings(elem_id=401)
    keys = [p["first"] for p in st.obj["m_mapDuctSystemTypeToSettings"]]
    assert keys == sorted(S.DUCT_SYSTEM_CLASSIFICATIONS)
    ps = S.pipe_settings(elem_id=402)
    assert [p["first"] for p in ps.obj["m_mapSystemTypeToPipeSettings"]] == \
        sorted(S.PIPE_SYSTEM_CLASSIFICATIONS)
    # servers default to none-selected (null GUID)
    assert ps.obj["m_pressLossCalcServerInfo"]["m_serverId"] == S.NULL_GUID
    for r in (ds, st, ps):
        assert r.roundtrip()["ok"]


def test_system_view_type_table_covers_19_families():
    tab = S.system_view_type_table(IdSource(500))
    idx = sorted(t.obj["m_systemFamilyIdx"] for t in tab)
    assert idx == [102, 103, 104, 105, 106, 107, 108, 109, 111, 112, 113, 114,
                   115, 116, 117, 118, 119, 120, 121]
    plans = {t.obj["m_systemFamilyIdx"]: t.obj["m_planViewDirection"] for t in tab}
    assert plans[109] == 0 and plans[111] == 1 and plans[102] == -1
    part = S.system_view_type_table(IdSource(600),
                                    skip_families=("3d", "floor_plan", "ceiling_plan"))
    assert len(part) == 16
    for t in tab:
        assert t.roundtrip()["ok"]


def test_small_singletons_roundtrip():
    ids = IdSource(800)
    recs = [
        S.auto_cam_settings(ids=ids), S.halftone_underlay_settings(ids=ids),
        S.multiple_values_indication_settings(ids=ids),
        S.workset_visibility_settings(ids=ids),
        S.worksharing_view_mode_settings(ids=ids),
        S.coordinate_system_display(ids=ids),
        S.active_geo_location_tracking(80, ids=ids),
        S.default_divide_settings(ids=ids), S.project_copy_settings(ids=ids),
        S.copy_watch_properties(ids=ids), S.area_settings(ids=ids),
        S.route_analysis_settings(ids=ids), S.mep_hidden_line_settings(ids=ids),
        S.fabrication_settings(ids=ids), S.fabrication_settings_element(ids=ids),
        S.sse_point_visibility_settings(ids=ids),
        S.reinforcement_settings(ids=ids), S.energy_data_settings(ids=ids),
        S.print_settings(ids=ids), S.gcs_tracker(ids=ids, units_id=81),
        S.area_measure("A", "d", 0, ids=ids),
    ] + list(S.revision_constellation(ids)) + list(S.model_graphics_styles(ids, 82))
    for cls in S.EMPTY_TRACKERS:
        recs.append(S.tracker(cls, ids=ids))
    for r in recs:
        rep = r.roundtrip()
        assert rep["ok"], (r.class_name, rep)
    # every empty tracker is exactly its listed body over a blank object
    csd = [r for r in recs if r.class_name == "CoordinateSystemDisplayElem"][0]
    assert csd.header["m_pBBox"]["value"]["m_minmax"] == [[0.0] * 3, [0.0] * 3]
    with pytest.raises(KeyError):
        S.tracker("NotATracker", elem_id=1)


def test_revision_constellation_wiring():
    recs = S.revision_constellation(IdSource(900))
    by = {r.class_name: r for r in recs}
    seqs = [r for r in recs if r.class_name == "RevisionNumberingSequence"]
    assert {s.obj["m_sequenceName"] for s in seqs} == {"Numeric", "Alphanumeric"}
    alpha = [s for s in seqs if s.obj["m_sequenceName"] == "Alphanumeric"][0]
    letters = [x["m_str"] for x in alpha.obj["m_oRevisionSettings"]["value"]["m_sequence"]]
    assert letters == [chr(ord("A") + i) for i in range(26)]
    tab = by["AllProjectRevisions"]
    rev = by["ProjectRevision"]
    assert tab.obj["m_revisionIds"] == [rev.elem_id]
    assert rev.obj["m_revisionNumberingSequenceId"] in {s.elem_id for s in seqs}
    assert [x["m_ref"]["classref"] for x in
            tab.header["m_parents"]["value"]["m_regenWildcards"]] == ["RevisionNumberingSequence"]


def test_no_cloned_payload_source():
    # the constructors must not read any .rvt / corpus file
    src = open(os.path.join(ROOT, "src/rvt/genesis/settings.py")).read()
    for banned in ("Document.load", "from_file(", "open_rvt(", "samples/", "extracted/"):
        assert banned not in src, banned
    # catalog.py: the ONLY corpus access is the documented enum derivation
    csrc = open(os.path.join(ROOT, "src/rvt/genesis/catalog.py")).read()
    assert csrc.count("Document.load") == 1
    assert "def derive_builtin_category_enum" in csrc


# ---------------------------------------------------------------------------
# tier 2: parametric reproduction of Autodesk specimens
# ---------------------------------------------------------------------------

def test_reproduce_pen_width_table_id2(rst):
    v = rst.value(2)
    t = v["m_pPenWidthTable"]["value"]
    model = {p["m_invertedScale"]: [x * 304.8 for x in p["m_pens"]]
             for p in t["m_modelPenInfo"]}
    persp = [x * 304.8 for x in t["m_perspectiveModelPenInfo"]["m_pens"]]
    draft = [x * 304.8 for x in t["m_draftPenInfo"]["m_pens"]]
    rec = S.pen_width_table(elem_id=2, model_pens_mm=model,
                            perspective_pens_mm=persp, annotation_pens_mm=draft)
    assert _diff(rec.obj, v) == []
    assert _diff(rec.header, rst.decode(2, 101).value) == []
    rep = rec.roundtrip()
    assert rep["ok"] and rep[102]["byte_exact"]


def test_reproduce_browser_organizations(rst, rme):
    for eid, kw in [
        (24945, dict(name="all", org_type=0, folders=[-1012106], sort_by=-1005112,
                     is_default=True, cell_list=True)),
        (24947, dict(name="not on sheets", org_type=0, folders=[-1012106],
                     sort_by=-1005112, cell_list=True,
                     filters=[{"param": -1005207, "value": "", "relation": 0}])),
        (26012, dict(name="Phase", org_type=0, folders=[-1012102, -1012106],
                     sort_by=-1005112, cell_list=True)),
        (26017, dict(name="Sheet Prefix", org_type=1, cell_list=True,
                     folders=[{"param": -1007401, "chars": 1}], sort_by=-1007401)),
        (1472524, dict(name="all", org_type=4, folders=[], sort_by=-1, is_default=True)),
        (1468599, dict(name="all", org_type=3, folders=[], sort_by=-1005112,
                       is_default=True)),
    ]:
        r = S.browser_organization(elem_id=eid, **kw)
        assert _diff(r.obj, rst.value(eid)) == [], eid
    # the two latest 'all' defaults reproduce the HEADER exactly too
    r = S.browser_organization("all", org_type=4, folders=[], sort_by=-1,
                               is_default=True, elem_id=1472524)
    assert _diff(r.header, rst.decode(1472524, 101).value) == []
    # rme's project-parameter organization (deletion set carries the params)
    r = S.browser_organization("Simple", org_type=0, folders=[142459], sort_by=-1005112,
                               filters=[{"param": 586533, "value": "Simple", "relation": 0}],
                               elem_id=709497)
    assert _diff(r.obj, rme.value(709497)) == []


def test_reproduce_struct_settings(rst):
    v = rst.value(54663)
    IN = 12.0
    st = {"parallel_brace_offset_in": v["m_parallelBraceOffset"] * IN,
          "symbolic_cutback_in": v["m_symbolicCutback"] * IN,
          "symbolic_brace_cutback_in": v["m_symbolicBraceCutback"] * IN,
          "column_cutback_in": v["m_columnCutback"] * IN,
          "analytical_snap_ft": v["m_analyticalModelSnapDistance"],
          "tolerance_support_ft": v["m_toleranceSupport"],
          "tolerance_discrepancy_ft": v["m_toleranceDiscrepancy"],
          "tolerance_autofix_xy_ft": v["m_toleranceAutofixXY"],
          "tolerance_autofix_z_ft": v["m_toleranceAutofixZ"],
          "bc_symbol_spacing_in": v["m_bcSpacing"] * IN,
          "point_loads_slope": v["m_scaledPointLoadsIntensitySlope"],
          "line_loads_slope": v["m_scaledLineLoadsIntensitySlope"],
          "area_loads_slope": v["m_scaledAreaLoadsIntensitySlope"],
          "loads_y_intercept": v["m_scaledLoadsIntensityYIntercept"],
          "min_load_force": v["m_minLoadForce"], "max_load_force": v["m_maxLoadForce"],
          "brace_repr_type": v["m_braceReprType"],
          "show_brace_above": v["m_showBraceAbove"],
          "show_brace_below": v["m_showBraceBelow"]}
    rec = S.struct_settings(elem_id=54663, settings=st,
                            bc_fixed_family_id=v["m_bcFixedFamilyId"],
                            show_analytical_nodes=v["m_showAnalyticalNodes"],
                            use_loads_display_scaling=v["m_useLoadsDisplayScaling"],
                            boundary_setback_disabled_for_steel=v["m_boundarySetbackDisabledForSteelElements"],
                            auto_support=v["m_autoSupport"], auto_consistency=v["m_autoConsistency"],
                            check_analytical_model_asset=v["m_checkAnalyticalModelAsset"])
    assert _diff(rec.obj, v) == []
    assert _diff(rec.header, rst.decode(54663, 101).value) == []


def test_reproduce_small_singletons(rst):
    cases = [
        (S.wall_join_default_setting(elem_id=102105), 102105),
        (S.auto_join_tracker(elem_id=102467), 102467),
        (S.initial_view_settings(elem_id=133303, initial_view_id=1456977), 133303),
        (S.reconcile_browser_settings(elem_id=116120, old_orphan_color=32768,
                                     new_orphan_color=32768), 116120),
        (S.keynoting_system(86291, elem_id=86315), 86315),
        (S.auto_cam_settings(elem_id=102842), 102842),
        (S.multiple_values_indication_settings(elem_id=1471489), 1471489),
        (S.active_geo_location_tracking(111428, active_geo_location_id=21748,
                                        elem_id=113109), 113109),
        (S.default_divide_settings(elem_id=907053), 907053),
        (S.project_copy_settings(elem_id=115987), 115987),
        (S.sse_point_visibility_settings(elem_id=1471913), 1471913),
        (S.area_settings(elem_id=85092), 85092),
        (S.fabrication_settings(elem_id=1218727), 1218727),
        (S.fabrication_settings_element(elem_id=1457285), 1457285),
        # (GCSTracker's specimen caches the sample's grid intersections; ours
        #  is the empty tracker of a grid-free base -- header wiring tested below)
        (S.tracker("MEPSystemTracker", elem_id=130510,
                   regen_only=[102127, 102128, 907354, 1218550]), 130510),
        (S.tracker("MEPNetworkTracker", elem_id=1468014,
                   regen_only=[102127, 102128, 907354, 1471901]), 1468014),
        (S.tracker("MEPNetworkDataElem", elem_id=1471901, regen_only=[1468014]), 1471901),
        (S.tracker("AssemblyTracker", elem_id=132328), 132328),
        (S.tracker("LayoutNodesTracker", elem_id=1218550, regen_only=[907354]), 1218550),
        (S.tracker("SheetsInSheetCollectionTracker", elem_id=1472007), 1472007),
        (S.tracker("AnalyticalToPhysicalRelationManager", elem_id=1471770), 1471770),
        (S.tracker("ReactionsUpToDateElem", elem_id=85104), 85104),
        (S.tracker("GraphicsCache", elem_id=1471712), 1471712),
        (S.tracker("StructuralConnectionSettings", elem_id=1462521), 1462521),
    ]
    for rec, eid in cases:
        d = _diff(rec.obj, rst.value(eid))
        assert d == [], (rec.class_name, eid, d[:3])
    # the GCS tracker's regeneration wiring (its cached grid data is the
    # sample's; a grid-free base has none): regenOnly = the units element
    gcs = S.gcs_tracker(elem_id=103632, units_id=19236)
    par = gcs.header["m_parents"]["value"]
    ref = rst.decode(103632, 101).value["m_parents"]["value"]
    assert par["m_regenOnly"] == ref["m_regenOnly"] == [19236]
    assert par["m_regenWildcards"] == ref["m_regenWildcards"]
    # header exactness for the trackers whose wiring we model
    for rec, eid in cases:
        if rec.class_name in ("MEPSystemTracker", "MEPNetworkTracker",
                              "MEPNetworkDataElem", "LayoutNodesTracker",
                              "AutoJoinTracker", "WallJoinDefaultSetting",
                              "InitialViewSettings", "ReconcileBrowserSettingsElem",
                              "ActiveGeoLocationTrackingElement", "AreaSettingsElem",
                              "MultipleValuesIndicationSettings"):
            h = _diff(rec.header, rst.decode(eid, 101).value)
            assert h == [], (rec.class_name, eid, h[:3])


def test_reproduce_construction_set_project(rst):
    v = rst.value(99928)
    cons = {k: v[f] for k, f in S._CS_FIELDS.items()}
    r = S.construction_set_project(elem_id=99928, constructions=cons,
                                   shading_factor=v["m_dShadingFactor"])
    assert _diff(r.obj, v) == []


def test_reproduce_mep_settings(rme):
    # wire settings (its own values, incl. the annotation family ids)
    v = rme.value(293123)
    t = v["m_wireTickMarkStyle"]
    r = S.wire_settings(elem_id=293123,
                        tick_mark_families={"hot": t["m_hotConductorFamSymId"],
                                            "neutral": t["m_neutralConductorFamSymId"],
                                            "ground": t["m_groundConductorFamSymId"],
                                            "slanted": t["m_bDrawSlantedLine"]},
                        connector_separator=v["m_strElectricalConnectorSeparator"],
                        crossing_gap_mm=v["m_dWiringCrossingGap"] * 304.8,
                        home_run_arrow_style_id=v["m_idWireHomeRunArrowLeaderStyle"],
                        show_tick_marks=v["m_eShowTickMarks"],
                        tick_mark_style=v["m_nWireTickMarkStyle"],
                        electrical_data_style=v["m_nElectricalDataStyle"],
                        circuit_description_style=v["m_nCircuitDescriptionStyle"],
                        home_run_arrow_count_style=v["m_eWireHomeRunArrowCountStyle"])
    assert _diff(r.obj, v) == []
    assert _diff(r.header, rme.decode(293123, 101).value) == []
    # conduit + cable tray settings
    for eid, fn, key in ((638851, S.conduit_settings, "m_strSizePrefix"),
                         (638850, S.cable_tray_settings, "m_strSizeSeparator")):
        v = rme.value(eid)
        kw = dict(connector_separator=v["m_strConnectorSeparator"],
                  size_suffix=v["m_strSizeSuffix"],
                  fitting_annotation_size_in=v["m_dFittingAnnotationSize"] * 12,
                  rise_drop_annotation_size_in=v["m_dRiseDropAnnotationSize"] * 12,
                  one_line_drop_type=v["m_e1LineDropType"],
                  one_line_rise_type=v["m_e1LineRiseType"],
                  contour_drop_type=v["m_eContourDropType"],
                  contour_rise_type=v["m_eContourRiseType"],
                  use_anno_scale_for_1line=v["m_bUseAnnoScaleFor1LineFittings"])
        if key == "m_strSizePrefix":
            kw["size_prefix"] = v[key]
        else:
            kw["size_separator"] = v[key]
        r = fn(elem_id=eid, **kw)
        assert _diff(r.obj, v) == [], eid
        assert _diff(r.header, rme.decode(eid, 101).value) == [], eid


def test_reproduce_pipe_and_duct_settings(rme):
    v = rme.value(293122)
    routing = {p["first"]: {"offset_ft": p["second"]["m_dOffset"],
                           "min_length_ft": p["second"]["m_dMinLength"],
                           "branch_offset_ft": p["second"]["m_dBranchOffset"],
                           "perimeter_inset_ft": p["second"]["m_dPerimeterInsetLength"],
                           "type_id": p["second"]["m_typeId"],
                           "branch_type_id": p["second"]["m_branchTypeId"]}
               for p in v["m_mapSystemTypeToPipeSettings"]}
    r = S.pipe_settings(
        elem_id=293122, size_suffix=v["m_strPipeSizeSuffix"],
        size_prefix=v["m_strPipeSizePrefix"],
        connector_separator=v["m_strPipeConnectorSeparator"],
        system_routing=routing, slopes_in_per_ft=v["m_pipeSlopes"],
        specific_angles_deg=[a["first"] for a in v["m_specificAngles"]],
        fitting_annotation_size_in=v["m_dPipeFittingAnnotationSize"] * 12,
        rise_drop_annotation_size_in=v["m_dPipeRiseDropAnnoSize"] * 12,
        elbow_increment_deg=math.degrees(v["m_dPipeElbowIncrementAngle"]),
        connector_tolerance_deg=math.degrees(v["m_dPipeConnectorTolerance"]),
        contour_rise_type=v["m_eDipingContourRiseType"],
        contour_drop_type=v["m_eDipingContourDropType"],
        one_line_bend_rise_type=v["m_eDiping1LineBendRiseType"],
        one_line_bend_drop_type=v["m_eDiping1LineBendDropType"],
        one_line_junction_rise_type=v["m_eDiping1LineJunctionRiseType"],
        one_line_junction_drop_type=v["m_eDiping1LineJunctionDropType"],
        fitting_angle_usage=v["m_fittingAngleUsage"],
        use_anno_scale_for_1line=v["m_bPipeUseAnnoScaleFor1LineFittings"],
        allow_conversion_per_system=v["m_bPipeAllowConversionSettingsPerSystemType"],
        closed_loop_hydronic_analysis=v["m_enableAnalysisForClosedLoopHydronicPipingNetworks"],
        pressure_loss_server=v["m_pressLossCalcServerInfo"],
        flow_conversion_server=v["m_flowConvertionServerInfo"])
    assert _diff(r.obj, v) == []
    assert _diff(r.header, rme.decode(293122, 101).value) == []
    v = rme.value(293121)
    routing = {p["first"]: {"main_offset_ft": p["second"]["m_dMainOffset"],
                           "main_min_length_ft": p["second"]["m_dMainMinLength"],
                           "branch_offset_ft": p["second"]["m_dBranchOffset"],
                           "branch_min_length_ft": p["second"]["m_dBranchMinLength"],
                           "branch_flex_max_ft": p["second"]["m_dBranchFlexMaxLength"],
                           "perimeter_inset_ft": p["second"]["m_dPerimeterInsetLength"],
                           "main_type_id": p["second"]["m_mainTypeId"],
                           "branch_type_id": p["second"]["m_branchTypeId"],
                           "branch_flex_type_id": p["second"]["m_branchFlexTypeId"]}
               for p in v["m_mapDuctSystemTypeToSettings"]}
    r = S.duct_settings(
        elem_id=293121, connector_separator=v["m_strDuctConnectorSeparator"],
        size_separator=v["m_strDuctSizeSeparator"],
        oval_separator=v["m_strOvalDuctSizeSeparator"],
        round_size_suffix=v["m_strRoundDuctSizeSuffix"], system_routing=routing,
        rise_drop_by_shape={p["first"]: p["second"] for p in v["m_mapDuctRiseDropSettings"]},
        specific_angles_deg=[a["first"] for a in v["m_specificAngles"]],
        air_density_kg_m3=v["m_dAirDensity"] / S._KG_M3_TO_INTERNAL,
        air_viscosity_pa_s=v["m_airDynamicViscosity"] / S._PA_S_TO_INTERNAL,
        elbow_increment_deg=math.degrees(v["m_dDuctElbowIncrementAngle"]),
        fitting_annotation_size_in=v["m_dDuctFittingAnnotationSize"] * 12,
        rise_drop_annotation_size_in=v["m_dDuctRiseDropAnnoSize"] * 12,
        flex_duct_length_ft=v["m_dFlexDuctLength"],
        fitting_angle_usage=v["m_fittingAngleUsage"],
        allow_conversion_per_system=v["m_bDuctAllowConversionSettingsPerSystemType"],
        network_based_calculations=v["m_enableNetworkBasedCalculations"],
        use_anno_scale_for_1line=v["m_bDuctUseAnnoScaleFor1LineFittings"],
        pressure_loss_server=v["m_pressLossCalcServerInfo"])
    assert _diff(r.obj, v) == []


def test_reproduce_size_tables(rme):
    v = rme.value(293120)                                   # duct sizes
    byshape = {p["first"]: [s["m_dSize"] * 12 for s in p["second"]["m_sizeData"]]
               for p in v["m_shapeSizes"]}
    r = S.duct_sizes(elem_id=293120, rectangular_in=byshape[0], oval_in=byshape[1],
                     round_in=byshape[2])
    assert _diff(r.obj, v) == []
    v = rme.value(293159)                                   # pipe sizes
    mmap = {}
    for pm in v["m_materialMapConnections"]:
        conns = {}
        for pc in pm["second"]["m_connectionMapSchedules"]:
            sch = {}
            for ps in pc["second"]["m_scheduleMapSizes"]:
                sch[ps["first"]] = [{"nominal_in": x["m_dSize"] * 12,
                                    "inner_in": x["m_dInnerDiameter"] * 12,
                                    "outer_in": x["m_dOuterDiameter"] * 12,
                                    "in_size_list": x["m_bInSizeList"],
                                    "used_by_sizing": x["m_bUsedBySizing"]}
                                   for x in ps["second"]["m_sizeData"]]
            conns[pc["first"]] = sch
        mmap[pm["first"]] = conns
    r = S.pipe_sizes(mmap, elem_id=293159)
    assert _diff(r.obj, v) == []


def test_reproduce_wire_sizes(rme):
    v = rme.value(293190)
    mt = {}
    for pm in v["m_mapMaterials"]:
        trs = {}
        for tr in pm["second"]["m_mapTemperatureRatings"]:
            corr = next(c["second"]["m_arrFactors"] for c in
                        pm["second"]["m_mapCorrectionFactors"] if c["first"] == tr["first"])
            trs[tr["first"]] = {
                "sizes": [(w["m_strSize"], w["m_dAmpacity"], w["m_dDiameter"] * 12,
                           bool(w["m_bInUse"])) for w in tr["second"]["m_arrWireSizes"]],
                "insulation_ids": tr["second"]["m_setInsulationIds"],
                "correction": [(f["m_dMin"] - 273.15, f["m_dMax"] - 273.15, f["m_dFactor"])
                               for f in corr]}
        mt[pm["first"]] = {"temperature_ratings": trs,
                           "ground_sizes": [(g["first"], g["second"])
                                            for g in pm["second"]["m_mapGroundSizes"]]}
    pf = {}
    for pm in v["m_mapPowerFactors"]:
        pf[pm["first"]] = {pp["first"]: {e["first"]: [(x["first"], x["second"])
                                          for x in e["second"]["m_arrEntries"]]
                             for e in pp["second"]["m_mapPowerFactors"]}
                            for pp in pm["second"]["m_mapPoles"]}
    diam = {p["first"]: p["second"] * 12 for p in v["m_mapWireDiameters"]}
    r = S.wire_sizes(mt, elem_id=293190, power_factor_tables=pf,
                     wire_diameters_in=diam, initialized=v["m_bInitialized"])
    assert _diff(r.obj, v) == []
    assert _diff(r.header, rme.decode(293190, 101).value) == []


def test_reproduce_keynote_table_3840_rows(rst):
    v = rst.value(86291)
    tbl = v["m_oKeyBasedTreeEntries"]["value"]
    entries = [(e["m_oEntry"]["value"]["m_key"], e["m_oEntry"]["value"]["m_parentKey"],
                e["m_oEntry"]["value"]["m_keynoteText"])
               for e in tbl["m_keyBasedTreeEntrySet"]]
    r = S.keynote_table(elem_id=86291, entries=entries, name=v["m_name"],
                        built_in=v["m_isBuiltIn"],
                        last_read_succeeded=v["m_lastReadSucceeded"])
    assert _diff(r.obj["m_oKeyBasedTreeEntries"], v["m_oKeyBasedTreeEntries"]) == []
    rest = [x for x in _diff(r.obj, v) if not x[0].startswith(".m_cellList")]
    assert rest == []


def test_reproduce_system_navigator_frame(rst):
    cats = rst.value(69851)["m_oaDrawFilters"][0]["value"]["m_categoryIds"]
    recs = S.system_navigator(IdSource(69851), phase_id=86961, sun_settings_id=54520,
                              invisible_style_id=201, not_silhouette_style_id=55150,
                              viewport_type_id=324, excluded_categories=cats)
    view, viewer, viewport, drawing = recs
    # viewer / viewport / drawing bodies exact; the view except the sample's
    # link-override map (a Revit link) and one ground-colour default
    assert _diff(viewer.obj, rst.value(69852)) == []
    assert _diff(viewport.obj, rst.value(69853)) == []
    assert _diff(drawing.obj, rst.value(69854)) == []
    d = _diff(view.obj, rst.value(69851))
    paths = {p for p, *_ in d}
    assert paths <= {".m_pRvtLinkOverrides.value.m_displaySettingsMap",
                     ".m_pViewDisplayMgr.value.m_background.m_groundColor"}, d
    assert _diff(viewer.header, rst.decode(69852, 101).value) == []
    assert _diff(drawing.header, rst.decode(69854, 101).value) == []


def test_reproduce_revisions_and_print(rst):
    seqs = S.revision_numbering_sequences(IdSource(1471493))
    assert _diff(seqs[0].obj, rst.value(1471493)) == []
    rev = S.project_revision(elem_id=49030, sequence_id=1471493, sequence_number=1,
                             description="Revision 1", date="Date 1", number="1")
    assert _diff(rev.obj, rst.value(49030)) == []
    tab = S.all_project_revisions([49030], 1471493, 1471494, elem_id=49031,
                                  min_cloud_spacing_ft=0.06561679790026247)
    assert _diff(tab.obj, rst.value(49031)) == []
    assert _diff(tab.header, rst.decode(49031, 101).value) == []
    v = rst.value(19895)
    p = v["m_PrintParameters"]
    r = S.print_settings(v["m_name"], elem_id=19895, paper_size=p["m_strPaperSize"],
                         paper_source=p["m_strPaperSource"],
                         paper_size_index=p["m_nPaperIndex"],
                         paper_dims_tenths_mm=(p["m_nPaperSizeX"], p["m_nPaperSizeY"]),
                         orientation=p["m_OrientationType"], zoom_pct=p["m_nZoom"],
                         dpi=p["m_nUserDPI"],
                         timestamp=v["m_timeStampInSeconds"]["m_lsb"], cell_list=True)
    assert _diff(r.obj, v) == []


def test_reproduce_area_measure_and_reinforcement(rst):
    v = rst.value(9490)
    r = S.area_measure(v["m_areaElemName"], v["m_areaElemDescription"], v["m_eAreaType"],
                       elem_id=9490, area_type_ids=v["m_areaTypeElemSet"],
                       plan_topology_id=v["m_areaSchemePlanTopologyElemId"],
                       default_space_id=v["m_defaultSpaceElemId"])
    assert _diff(r.obj, v) == []
    v = rst.value(137426)
    abbr = [(x["value"]["m_oSetting"]["value"]["m_str"],
             x["value"]["m_oValue"]["value"]["m_str"],
             x["value"]["m_resourceId"], x["value"]["m_typeTag"])
            for x in v["m_abbreviationItems"]]
    r = S.reinforcement_settings(elem_id=137426, abbreviations=abbr,
                                 varying_length_suffix=v["m_rebarVaryingLengthNumberSuffix"])
    d = [x for x in _diff(r.obj, v) if not x[0].startswith(".m_cellList")]
    assert d == []
    # our default slot names + resource ids match the fixed built-in slots
    ours = S.reinforcement_settings(elem_id=1)
    got = [(x["value"]["m_oSetting"]["value"]["m_str"], x["value"]["m_resourceId"],
            x["value"]["m_typeTag"]) for x in ours.obj["m_abbreviationItems"]]
    ref = [(x["value"]["m_oSetting"]["value"]["m_str"], x["value"]["m_resourceId"],
            x["value"]["m_typeTag"]) for x in v["m_abbreviationItems"]]
    assert got == ref                      # slots identical (interface) ...
    ourv = [x["value"]["m_oValue"]["value"]["m_str"] for x in ours.obj["m_abbreviationItems"]]
    theirv = [x["value"]["m_oValue"]["value"]["m_str"] for x in v["m_abbreviationItems"]]
    assert ourv != theirv                 # ... but the abbreviation VALUES are ours


def test_reproduce_view_type_definitions(rst):
    from rvt.genesis import skeleton as sk
    el = sk.new_view_type(49552, "Floor Plan", "floor_plan")
    el.obj["m_calloutAttrId"] = 49508
    assert _diff(el.obj, rst.value(49552)) == []
    el = sk.new_view_type(1470382, "Analysis Report", "analysis_report")
    d = [x for x in _diff(el.obj, rst.value(1470382)) if not x[0].startswith(".m_cellList")]
    assert d == []


# ---------------------------------------------------------------------------
# tier 3: the built-in category enum + the complete style catalog
# ---------------------------------------------------------------------------

def test_builtin_category_enum_is_frozen_and_shaped():
    enum = C.load_builtin_category_enum(derive_if_missing=False)
    assert enum["count"] == 1074 and enum["cuttable"] == 333
    ids = [c["id"] for c in enum["categories"]]
    assert ids == sorted(ids) and all(i < 0 for i in ids)
    assert -2000011 in ids                   # OST_Walls is in the graphic enum


@pytest.mark.skipif(not _have_corpus, reason="corpus not extracted")
def test_builtin_category_enum_matches_a_fresh_derivation():
    frozen = C.load_builtin_category_enum(derive_if_missing=False)
    fresh = C.derive_builtin_category_enum(verbose=False)
    assert fresh["count"] == frozen["count"] and fresh["cuttable"] == frozen["cuttable"]
    assert [c["id"] for c in fresh["categories"]] == [c["id"] for c in frozen["categories"]]


def test_catalog_generates_full_table_and_roundtrips():
    recs = C.builtin_style_catalog(IdSource(2_000_000))
    assert len(recs) == 1074 + 333
    types = sorted(set(r.obj["m_gstyleType"] for r in recs))
    assert types == [1, 2]
    rep = C.catalog_report(recs)
    assert rep["roundtrip_ok"] == rep["rows"]
    # exclusion of a base's categories completes rather than duplicates
    part = C.builtin_style_catalog(IdSource(3_000_000), exclude_categories=[-2000011])
    assert not any(r.obj["m_categoryId"] == -2000011 for r in part)
    assert len(part) == len(recs) - 2       # walls are cuttable: proj + cut removed


def test_catalog_discipline_rules():
    exp = C._explicit_disciplines()
    assert C.classify_category(-2000011, exp) == "architectural"    # walls (house)
    assert C.classify_category(-2008132, exp) == "electrical"       # conduit (house)
    assert C.classify_category(-2008044, exp) == "piping"           # pipes (MEP sub-range)
    assert C.classify_category(-2008000, exp) == "mechanical"       # ducts
    assert C.classify_category(-2009500, exp) == "structural"       # analytical band
    assert C.classify_category(-2004500, exp) == "annotation"
    sch = C.catalog_scheme()
    assert all(col != 0 for (_p, _c, col) in sch.values())        # no pure black rows


@pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "experiments", "genesis", "reference",
                                    "object_styles.autodesk-extracted.json")),
    reason="quarantined reference table absent")
def test_catalog_rows_are_never_value_identical_to_the_autodesk_table():
    """The assayer's diff, run as a guard: NO generated row may equal the
    quarantined Autodesk row (pen, colour, pattern, screen-sized) for its
    category -- the ids/type are the format constants, the values ours."""
    recs = C.builtin_style_catalog(IdSource(2_000_000))
    ours = {(r.obj["m_categoryId"], r.obj["m_gstyleType"]):
            (r.obj["m_pGStyle"]["value"]["m_penNumber"],
             r.obj["m_pGStyle"]["value"]["m_color"],
             r.obj["m_pGStyle"]["value"]["m_linePatternId"],
             r.obj["m_pGStyle"]["value"]["m_isScreenSized"]) for r in recs}
    with open(os.path.join(ROOT, "experiments", "genesis", "reference",
                           "object_styles.autodesk-extracted.json")) as fh:
        tab = json.load(fh)
    ident = 0
    for cat_s, ent in (tab.get("styles") or {}).items():
        for role, gt in (("projection", 1), ("cut", 2)):
            e = ent.get(role)
            if not e:
                continue
            key = (int(cat_s), gt)
            if key not in ours:
                continue
            pat = e.get("pattern_id") if e.get("pattern_id") is not None else LINEPATTERN_SOLID
            if ours[key] == (int(e.get("pen") or 0), int(e.get("color") or 0),
                             pat, bool(e.get("screen_sized"))):
                ident += 1
    assert ident == 0


# ---------------------------------------------------------------------------
# tier 4: ADocument registry population
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "experiments", "genesis",
                                                    "G1_candidate.rvt")),
                    reason="G1_candidate.rvt absent")
def test_apply_adoc_registry_over_the_candidate_document():
    from rvt import adocument as adoc
    from rvt.container import open_rvt
    path = os.path.join(ROOT, "experiments", "genesis", "G1_candidate.rvt")
    with open_rvt(path) as f:
        payload = f.inflate(adoc.STREAM, 0)
    src = adoc.decode_latest(payload)
    assert src.clean
    maps_path = os.path.join(ROOT, "experiments", "genesis", "G1_registry_maps.json")
    maps = json.load(open(maps_path)) if os.path.exists(maps_path) else {}
    cat = S.standard_settings(IdSource(9_000_000), tier="all",
                              doc_ids={"units": 1500184, "document_sun": 1500204,
                                       "phase_new": 1500197, "phase_filter": 1500198,
                                       "geo_location": 1500189, "level1": 1500193,
                                       "phase_set": 1500195})
    tree = src.value
    rep = S.apply_adoc_registry(tree, cat.records, maps=maps)
    applied = rep["applied"]
    assert applied.get("uet", 0) >= 30           # our singletons in their slots
    assert applied.get("browser", 0) == 6
    assert applied.get("navigator", 0) == 1
    assert applied.get("appinfo", 0) >= 3
    # named surfaces populated
    body = S._appinfo_body(tree, "PenWidthTableInfo")
    pen = [r for r in cat.records if r.class_name == "PenWidthTableElem"][0]
    assert body["m_penWidthTableElemId"] == pen.elem_id
    bo = S._appinfo_body(tree, "BrowserOrganizationTracking")
    assert len(bo["m_currentBrOrgTypeToBrOrgMap"]) == 4
    dbv = S._appinfo_body(tree, "DBViewInfo")
    nav = [r for r in cat.records if r.class_name == "RbsDbViewSystemNavigator"][0]
    assert dbv["m_DBViewSystemNavigatorId"] == nav.elem_id
    # the edited tree re-encodes and re-decodes identically
    payload2 = adoc.encode_latest(tree)
    back = adoc.decode_latest(payload2)
    assert back.clean and back.value == tree


# ---------------------------------------------------------------------------
# tier 5: the S-ladder deliverables (when built)
# ---------------------------------------------------------------------------

def test_probes_manifest_consistency():
    p = os.path.join(SINGLETONS_DIR, "probes.json")
    if not os.path.exists(p):
        pytest.skip("probes.json not built (run build_ladder.py)")
    m = json.load(open(p))
    rungs = [x["rung"] for x in m["probes"]]
    assert rungs == ["S1", "S2", "S3", "S4", "S5"]
    if not any(os.path.exists(os.path.join(ROOT, x["file"]))
               for x in m["probes"]):
        pytest.skip("probe binaries are git-ignored and absent (fresh clone)")
    for x in m["probes"]:
        assert x["tests_one_thing"] and x["PASS_means"] and x["FAIL_means"]
        if x["verdict"] == "VALID":
            assert os.path.exists(os.path.join(ROOT, x["file"]))


@pytest.mark.parametrize("rung", ["S1", "S2", "S3", "S4", "S5"])
def test_ladder_files_validate_clean(rung):
    path = os.path.join(SINGLETONS_DIR, f"{rung}.rvt")
    if not os.path.exists(path):
        pytest.skip(f"{rung}.rvt not built (run build_ladder.py)")
    from rvt.validate import validate_file
    rep = validate_file(path)
    assert rep.ok and len(rep.errors) == 0, [e.message for e in rep.errors[:3]]


# ---------------------------------------------------------------------------
# tier 6: THE FIXER (2026-08-03) -- specimen-invariant lints for the two
# classes the linter method convicted on the PEN TABLE + the object-styles
# CATALOG (docs/inbox/genesis-fixer.md).  Each fixed constructor's DEFAULT
# output passes the fixer's own field diff with 0 hard findings, and the
# pre-fixer shape is provably rejected by the same lint (the lint bites).
# ---------------------------------------------------------------------------

SUBST_V2_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_v2")


def test_pen_scale_breakpoints_are_the_project_format_constant():
    # every 2026 project pen table (m_famId -1) carries exactly these six
    # inverted scales; ours must too (768 appeared in ZERO of 3,494 tables)
    assert S.PEN_SCALE_BREAKPOINTS == [10, 20, 50, 100, 200, 500]
    assert set(S.PEN_SCALE_SET) == {10, 20, 50, 100, 200, 500}
    rec = S.pen_width_table(elem_id=2)
    scales = [p["m_invertedScale"] for p in
              rec.obj["m_pPenWidthTable"]["value"]["m_modelPenInfo"]]
    assert scales == [10, 20, 50, 100, 200, 500]


def test_pen_table_default_lints_clean():
    rec = S.pen_width_table(elem_id=2)
    lint = S.lint_pen_width_table(rec)
    assert lint["ok"] and lint["hard"] == [], lint["hard"]
    # widths stay OURS (ISO 128) but inside the corpus width range
    lo, hi = S.PEN_WIDTH_MM_RANGE
    for pi in rec.obj["m_pPenWidthTable"]["value"]["m_modelPenInfo"]:
        mm_vals = [round(x * 304.8, 4) for x in pi["m_pens"]]
        assert all(lo <= w <= hi for w in mm_vals)
        assert mm_vals == sorted(mm_vals)


def test_pen_table_lint_bites_on_the_prefixer_shape():
    # the pre-fixer scale ladder (24..768) and a non-monotone vector both FAIL
    old_scales = {24: S.pen_series_mm(0), 48: S.pen_series_mm(1), 96: S.pen_series_mm(2),
                  192: S.pen_series_mm(3), 384: S.pen_series_mm(4), 768: S.pen_series_mm(5)}
    rec = S.pen_width_table(elem_id=2, model_pens_mm=old_scales)
    lint = S.lint_pen_width_table(rec)
    assert not lint["ok"]
    assert any("m_invertedScale" in f["field"] for f in lint["hard"])
    bad = S.pen_series_mm(0)[::-1]                      # descending widths
    rec2 = S.pen_width_table(elem_id=2, perspective_pens_mm=bad)
    lint2 = S.lint_pen_width_table(rec2)
    assert not lint2["ok"]
    assert any("monotone" in f["field"] for f in lint2["hard"])


@pytest.fixture(scope="module")
def style_profile():
    p = C.PROFILE_FILE
    if not os.path.exists(p):
        pytest.skip("style profile not frozen (python -m rvt.genesis.catalog --derive-profile)")
    with open(p) as fh:
        return json.load(fh)


def test_style_profile_is_frozen_and_shaped(style_profile):
    prof = style_profile
    keys = prof["keys"]
    assert prof["count"] == len(keys) == 1407
    assert prof["rows_analysed"] >= 8000
    low = set()
    for k, v in keys.items():
        cat, gt = k.split(":")
        assert int(cat) == v["cat"] and int(gt) == v["type"]
        assert v["cat"] < 0 and v["type"] in (1, 2)
        assert v["files"] == 6
        # the cell-list era bit is never part of our flag word
        assert v["ab"] & C.AB_CELLLIST_BIT == 0
        assert v["ab"] & 0x4000000, "every built-in style row carries 0x4000000"
        low.add(v["ab"] & 0xFF)
        assert v["pattern"] in ("null", "nullwire", "solid", "elem") or v["pattern"].startswith("builtin:")
        assert v["material"] in ("null", "nullwire", "elem") or v["material"].startswith("builtin:")
        assert v["pen"] in ("ours", "null0", "nullneg1")
        assert isinstance(v["screen_sized"], bool)
    assert low == {0x0E, 0x1E}                    # the per-category low byte
    s = prof["summary"]
    assert s["screen_sized_keys"] == 48
    assert s["pattern_rules"]["null"] >= 300      # ~380 keys have NO pattern cell
    # STRUCTURE ONLY: no colour is recorded anywhere in the profile
    assert "color" not in json.dumps(prof).lower()


def test_builtin_style_catalog_lints_clean(style_profile):
    recs = C.builtin_style_catalog(IdSource(4_000_000), profile=style_profile)
    assert len(recs) == 1407
    lint = C.lint_builtin_style_catalog(recs, profile=style_profile)
    assert lint["ok"] and lint["hard"] == [], lint["hard"][:5]
    # the ONLY soft findings are the document-wiring inputs (elem keys)
    assert {f["field"] for f in lint["soft"]} <= {"m_linePatternId", "m_materialElemId"}
    # per-key shape is applied: at least one null-pattern, one screen-sized,
    # one built-in-material and one null-pen row exist
    pats = sum(1 for r in recs if r.obj["m_pGStyle"]["value"]["m_linePatternId"] == INVALID)
    scr = sum(1 for r in recs if r.obj["m_pGStyle"]["value"]["m_isScreenSized"])
    bim = sum(1 for r in recs if r.obj["m_pGStyle"]["value"]["m_materialElemId"] < -1)
    pen0 = sum(1 for r in recs if r.obj["m_pGStyle"]["value"]["m_penNumber"] in (0, -1))
    assert pats >= 300 and scr == 48 and bim >= 30 and pen0 >= 38
    # header flag word: low bytes now split per category, cell-list bit clear
    lows = {r.header["m_abFlags4Bytes"] & 0xFF for r in recs}
    assert lows == {0x0E, 0x1E}
    assert all(not (r.header["m_abFlags4Bytes"] & C.AB_CELLLIST_BIT) for r in recs)
    # every row still round-trips clean + byte-exact
    rep = C.catalog_report(recs)
    assert rep["roundtrip_ok"] == rep["rows"]


def test_catalog_lint_bites_on_the_prefixer_shape(style_profile):
    # the pre-fixer uniform-shape table: the lint convicts thousands of fields
    old = C.builtin_style_catalog(IdSource(5_000_000), use_profile=False)
    lint = C.lint_builtin_style_catalog(old, profile=style_profile)
    assert not lint["ok"]
    assert len(lint["hard"]) > 2000
    fields = {f["field"].split("(")[0] for f in lint["hard"]}
    assert "hdr.m_abFlags4Bytes" in fields
    assert "m_linePatternId" in fields and "m_isScreenSized" in fields


def test_catalog_wiring_and_id_map(style_profile):
    # 'elem' keys take the caller's document wiring; id_map pins existing ids
    elem_pat = [(int(k.split(":")[0]), int(k.split(":")[1]))
                for k, v in style_profile["keys"].items() if v["pattern"] == "elem"]
    elem_mat = [(int(k.split(":")[0]), int(k.split(":")[1]))
                for k, v in style_profile["keys"].items() if v["material"] == "elem"]
    assert elem_pat and elem_mat
    kp, km = elem_pat[0], elem_mat[0]
    wiring = {kp: {"line_pattern_id": 555001}, km: {"material_id": 555002}}
    id_map = {kp: 777001}
    recs = C.builtin_style_catalog(IdSource(6_000_000), profile=style_profile,
                                   wiring=wiring, id_map=id_map)
    by = {(int(r.obj["m_categoryId"]), int(r.obj["m_gstyleType"])): r for r in recs}
    assert by[kp].obj["m_pGStyle"]["value"]["m_linePatternId"] == 555001
    assert by[km].obj["m_pGStyle"]["value"]["m_materialElemId"] == 555002
    # element (>0) references land in the header deletion set (the rule)
    assert 555001 in by[kp].header["m_parents"]["value"]["m_deletion"]
    assert 555002 in by[km].header["m_parents"]["value"]["m_deletion"]
    # id_map: the row is built AT the pinned id
    r = by[kp]
    assert r.elem_id == 777001 and r.obj["m_id"] == 777001
    assert 777001 in r.header["m_parents"]["value"]["m_deletion"]
    # wired rows lint clean as non-standalone (wiring resolves the soft finding)
    lint = C.lint_builtin_style_catalog([by[kp], by[km]], profile=style_profile,
                                        standalone=False)
    assert lint["hard"] == []


def test_style_profile_rules_hold_on_a_real_sample(rst, style_profile):
    # corpus tie-in: rstbasic's own 1,407 built-in rows obey the frozen
    # per-key STRUCTURAL rules (null pattern / null pen / screen-sized are
    # every-file invariants; the flag word is in the key's observed set)
    keys = style_profile["keys"]
    checked = pattern_null = screen = pen_null = ab_in_set = 0
    for gid in rst.ids_of_class("GStyleElem", host_only=True):
        v = rst.value(gid) or {}
        if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
            continue
        cid, gt = v.get("m_categoryId"), v.get("m_gstyleType")
        if not (isinstance(cid, int) and cid < 0):
            continue
        prof = keys[f"{cid}:{gt}"]
        gs = v["m_pGStyle"]["value"]
        checked += 1
        # STRICT rules are every-observation invariants -> hold in rstbasic
        if prof["pattern"] == "null":
            assert gs["m_linePatternId"] == INVALID
            pattern_null += 1
        elif prof["pattern"].startswith("builtin:"):
            assert gs["m_linePatternId"] == int(prof["pattern"].split(":", 1)[1])
        elif prof["pattern"] == "elem":
            assert isinstance(gs["m_linePatternId"], int) and gs["m_linePatternId"] > 0
        if prof["screen_sized"]:
            assert gs["m_isScreenSized"] is True
            screen += 1
        if prof["pen"] == "null0":
            assert gs["m_penNumber"] == 0
            pen_null += 1
        if prof["material"] == "null":
            assert gs["m_materialElemId"] == INVALID
        elif prof["material"].startswith("builtin:"):
            assert gs["m_materialElemId"] == int(prof["material"].split(":", 1)[1])
        elif prof["material"] == "elem":
            assert isinstance(gs["m_materialElemId"], int) and gs["m_materialElemId"] > 0
        h = rst.decode(gid, 101)
        if h and h.clean:
            ab = h.value["m_abFlags4Bytes"]
            assert ab in prof["ab_set"]
            ab_in_set += 1
    assert checked == 1407 and pattern_null >= 300 and screen == 48
    assert pen_null >= 38 and ab_in_set == 1407


def test_pen_table_scale_set_holds_on_real_samples(rst, rme):
    # both project pen tables (id 2, m_famId -1) carry exactly OUR scale set
    for doc in (rst, rme):
        v = doc.value(2)
        assert v.get("m_famId") == INVALID
        scales = [p["m_invertedScale"]
                  for p in v["m_pPenWidthTable"]["value"]["m_modelPenInfo"]]
        assert scales == S.PEN_SCALE_BREAKPOINTS


@pytest.mark.parametrize("probe", ["X_pen", "X_cat", "X1", "X6a"])
def test_v2_files_validate_clean(probe):
    path = os.path.join(SUBST_V2_DIR, f"{probe}.rvt")
    if not os.path.exists(path):
        pytest.skip(f"{probe}.rvt not built (run experiments/genesis/subst_v2/build_v2.py)")
    from rvt.validate import validate_file
    rep = validate_file(path)
    assert rep.ok and len(rep.errors) == 0, [e.message for e in rep.errors[:3]]


def test_v2_probes_manifest_consistency():
    p = os.path.join(SUBST_V2_DIR, "probes.json")
    if not os.path.exists(p):
        pytest.skip("subst_v2 probes.json not built (run build_v2.py)")
    m = json.load(open(p))
    names = [x["file"] for x in m["probes"]]
    assert any("X_pen" in n for n in names) and any("X_cat" in n for n in names)
    if not any(os.path.exists(os.path.join(ROOT, x["file"]))
               for x in m["probes"]):
        pytest.skip("probe binaries are git-ignored and absent (fresh clone)")
    for x in m["probes"]:
        assert x["tests_one_thing"] and x["passing_sibling"]
        assert x["PASS_means"] and x["FAIL_means"]
        if x.get("verdict") == "VALID":
            assert os.path.exists(os.path.join(ROOT, x["file"]))


def test_fixed_constructors_pass_rvt_objlint():
    """The linter stream's mined-invariant lint (rvt.objlint) reads 0
    findings on our FIXED pen table and catalog rows (object + header +
    seq-103 scope; the ElemTable vintage/id-band rules are ADD-PATH
    properties, out of a constructor's reach -- the in-place X_pen/X_cat
    probes hold them by construction).  The pre-fixer pen table trips the
    scale ENUM rule, proving the lint bites."""
    try:
        from rvt import objlint as OL
    except Exception:                                     # noqa: BLE001
        pytest.skip("rvt.objlint not available")
    invs = OL.load_invariants(["PenWidthTableElem", "GStyleElem"])
    if not invs:
        pytest.skip("objlint invariants not mined (python -m rvt.objlint)")
    rec = S.pen_width_table(elem_id=2)
    f = OL.lint_object("PenWidthTableElem", rec.obj, rec.header, invariants=invs,
                       seq103_class="SerializedDummy", elem_id=2)
    assert f == [], [(x.field_path, x.rule) for x in f]
    old_scales = {24: S.pen_series_mm(0), 48: S.pen_series_mm(1), 96: S.pen_series_mm(2),
                  192: S.pen_series_mm(3), 384: S.pen_series_mm(4), 768: S.pen_series_mm(5)}
    old = S.pen_width_table(elem_id=2, model_pens_mm=old_scales)
    fo = OL.lint_object("PenWidthTableElem", old.obj, old.header, invariants=invs,
                        seq103_class="SerializedDummy", elem_id=2)
    assert any("m_invertedScale" in x.field_path and x.rule == "ENUM" for x in fo)
    recs = C.builtin_style_catalog(IdSource(7_000_000))
    findings = []
    for r in recs:
        findings += OL.lint_object("GStyleElem", r.obj, r.header, invariants=invs,
                                   seq103_class="SerializedDummy", elem_id=r.elem_id)
    assert findings == [], [(x.field_path, x.rule) for x in findings[:5]]


def test_pen_table_feet_path_reproduces_specimen_bytes(rst):
    """The exact-value probe path: fed the specimen's own stored FEET
    values, the constructor's OBJECT re-encodes to the specimen's BYTES
    (the controls stream's P1: the mm interface cannot reach 8 of 128
    stored doubles; the feet path can, no post-patching)."""
    v = rst.value(2)
    t = v["m_pPenWidthTable"]["value"]
    model_ft = {p["m_invertedScale"]: p["m_pens"] for p in t["m_modelPenInfo"]}
    rec = S.pen_width_table(elem_id=2, model_pens_ft=model_ft,
                            perspective_pens_ft=t["m_perspectiveModelPenInfo"]["m_pens"],
                            annotation_pens_ft=t["m_draftPenInfo"]["m_pens"])
    from rvt.encode import ObjectEncoder
    from rvt.objects import ObjectDecoder
    dec = ObjectDecoder()
    enc = ObjectEncoder(decoder=dec)
    r = rst.record(2, 102)
    assert enc.encode_object(r.class_id, rec.obj) == r.payload
    assert _diff(rec.header, rst.decode(2, 101).value) == []

"""tests/test_port2024.py -- the genesis-2024 constructor portability layer.

Proves (1) the CONFIRMED three-way portability verdicts -- including every
place 2024 evolved DIFFERENTLY from 2025 (GeomStep absent-not-renamed,
DBViewDrafting's extra drop + 2024-only field, the AutoCam re-typing, the
duct-viscosity quantity change, the MEP tracker map re-typing, and the five
2025-era classes 2024 lacks); (2) the field-map hooks and the delegation
preconditions (the port2025 hooks reused verbatim are only reused where the
2024 layout equals 2025's -- asserted, not assumed); (3) adapt() round-trips
byte-exact under the 2024 schema, matches the 2024 corpus field shape, and
the specimen gate is BYTE-EXACT against Autodesk's own 2024 sample records;
(4) missing classes are refused honestly.  Sample-backed assertions skip
cleanly off the dev machine.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import port2024 as P24                              # noqa: E402
from rvt.genesis import port2025 as P25                              # noqa: E402
from rvt.genesis import types as T                                   # noqa: E402
from rvt.genesis.types import INVALID                                # noqa: E402

RST24 = os.path.join(ROOT, "samples", "2024", "rstbasicsampleproject.rvt")
needs_sample = pytest.mark.skipif(not os.path.exists(RST24),
                                  reason="quarantined 2024 samples not present")
pytestmark = pytest.mark.usefixtures("no_release_leak")   # the sample rows enter versions.reading in-process


# ---------------------------------------------------------------------------
# 1. the CONFIRMED portability verdicts (three-way)
# ---------------------------------------------------------------------------
def test_missing_2024_includes_conductor_catalog_and_2025_era_classes():
    for cls in P24.MISSING_2024_CONSTRUCTED:
        assert P24.diff_class(cls)["verdict"] == "MISSING-2024", cls
        assert not P24.exists_2024(cls)
    # the five 2025-era classes are the NON-monotonic part: 2025 HAS them
    for cls in ("SheetCollection", "SheetsInSheetCollectionTracker",
                "MEPNetworkDataElem", "STEPExportSettings",
                "BuildingOperatingYearSchedule"):
        assert P25.exists_2025(cls), cls


def test_machinery_layer_ports():
    for cls in ("ADocument", "Element", "Symbol", "GElement", "SerializedDummy",
                "ElemTable", "ElemRec", "DocumentHistory",
                "DocumentIncrementTable", "PartitionTable"):
        assert P24.diff_class(cls)["verdict"] == "IDENTICAL", cls
    # 2024-specific: ElementHeader / FamilyInstance are VERSION-ONLY (v25->24,
    # v39->37) -- free, records carry no version (2025 had them IDENTICAL)
    d = P24.diff_class("ElementHeader")
    assert d["verdict"] == "VERSION-ONLY" and d["version_2024"] == 24
    assert P24.diff_class("FamilyInstance")["verdict"] == "VERSION-ONLY"


def test_2025_era_layout_deltas_still_hold_in_2024():
    for cls in ("GeomTable", "RbsWireType", "RbsWireSettingsElem",
                "RbsWireSizesElem", "NumberingSchema", "BrowserOrganization",
                "ModelGraphicsStyle", "ViewDisplayMgr", "AssemblyCodeTable",
                "KeynoteTable", "StructSettingsElem", "ReinforcementSettings",
                "VertCompoundStructureGStep", "DatumPlaneGeomStep",
                "CoordinateElemBaseGeomStep", "MakeCutterForPlanRegionsGStep",
                "ViewerGStep", "DBView", "DBViewDrafting", "Viewport",
                "BrowserOrganizationTracking"):
        assert P24.diff_class(cls)["verdict"] == "LAYOUT-DELTA", cls


def test_deltas_2024_gained_over_2025():
    """Classes IDENTICAL in 2025 that 2024 changes -- each one's 2024 layout
    established independently."""
    for cls in ("AutoCamSettingsElem", "RbsDuctSettingsElem", "MEPNetworkTracker",
                "RbsDistributionSysType", "HVACLoadScheduleElem",
                "IndependentTag", "KeynoteTag"):
        assert P24.diff_class(cls)["verdict"] == "LAYOUT-DELTA", cls
        assert P25.diff_class(cls)["verdict"] == "IDENTICAL", cls
    # Rebar: VERSION-ONLY in 2025, real delta in 2024 (m_frozenSegments)
    assert P25.diff_class("Rebar")["verdict"] == "VERSION-ONLY"
    d = P24.diff_class("Rebar")
    assert d["verdict"] == "LAYOUT-DELTA"
    assert any("m_frozenSegments" in (x.get("only_2026") or []) for x in d["deltas"])


def test_geomstep_2024_has_no_extra_data_field_at_all():
    """THE non-monotonic headline: 2025 RENAMED m_oExtraDatas->m_oExtraData;
    2024 predates the field entirely.  The port2025 rename hook must NOT be
    carried."""
    d = P24.diff_class("GeomStep")
    assert d["version_2024"] == 15
    base = next(x for x in d["deltas"] if x["base"] == "GeomStep")
    assert base["only_2026"] == ["m_oExtraDatas"]
    assert base["only_2024"] == []                       # no renamed twin
    assert ("GeomStep", "m_oExtraData") in P25.HOOKS     # 2025 carries the rename
    assert ("GeomStep", "m_oExtraData") not in P24.HOOKS_2024
    assert ("GeomStep", "m_oExtraDatas") not in P24.HOOKS_2024


def test_dbviewdrafting_2024_delta_differs_from_2025():
    d = P24.diff_class("DBViewDrafting")
    assert d["version_2024"] == 11
    own = next(x for x in d["deltas"] if x["base"] == "DBViewDrafting")
    assert set(own["only_2026"]) == {"m_sheetCollectionId", "m_sheetTitleBlockId"}
    assert own["only_2024"] == ["m_scheduleInstanceIds"]
    # 2025 only dropped the title block id
    d25 = P25.diff_class("DBViewDrafting")
    own25 = next(x for x in d25["deltas"] if x["base"] == "DBViewDrafting")
    assert own25["only_2026"] == ["m_sheetTitleBlockId"]
    # the DBView base delta (m_viewPositionId) is shared with 2025
    base = next(x for x in d["deltas"] if x["base"] == "DBView")
    assert base["only_2026"] == ["m_viewPositionId"]


def test_viewport_and_browser_tracking_match_2025_layout():
    d = P24.diff_class("Viewport")
    assert d["version_2026"] == 13 and d["version_2024"] == 10
    only = [f for x in d["deltas"] for f in (x.get("only_2026") or [])]
    assert set(only) >= {"m_viewPosition", "m_viewAnchor"}
    d = P24.diff_class("BrowserOrganizationTracking")
    assert d["version_2024"] == 5
    only24 = [f for x in d["deltas"] for f in (x.get("only_2024") or [])]
    assert set(only24) >= {"m_currentBrOrgViews", "m_currentBrOrgSheets",
                           "m_currentBrOrgSchedules"}


def test_vs_2025_annotations():
    assert P24.vs_2025("GeomStep") == "differs-from-2025"
    assert P24.vs_2025("DBViewDrafting") == "differs-from-2025"
    assert P24.vs_2025("GeomTable") == "same-as-2025"
    assert P24.vs_2025("BrowserOrganizationTracking") == "same-as-2025"
    assert P24.vs_2025("Viewport") == "same-as-2025"
    assert P24.vs_2025("AutoCamSettingsElem") == "2025=IDENTICAL"
    assert P24.vs_2025("SheetCollection") == "2025=IDENTICAL"


def test_delegated_numbering_hooks_precondition_layouts_identical_2024_2025():
    """port2024 delegates the two NumberingSchema hooks to port2025 (they
    build 2025-blank ParameterBasedPartitionDescriptionCreator /
    NumberingSchemaType bodies).  Sound ONLY because those layouts are
    identical 2024==2025 -- asserted here so drift fails loudly."""
    d24, _e24, s24 = P24._S24()
    d25, _e25, s25 = P25._S25()
    for cls in ("ParameterBasedPartitionDescriptionCreator", "NumberingSchemaType"):
        c24, c25 = s24.by_name[cls], s25.by_name[cls]
        f24 = [(c.name, P24._field_sig(f, s24)) for c in d24.chain(c24.type_id)
               for f in c.fields]
        f25 = [(c.name, P25._field_sig(f, s25)) for c in d25.chain(c25.type_id)
               for f in c.fields]
        assert f24 == f25, cls
    # and the 2024-mined GUID table equals the 2025 one the delegated hook uses
    assert P24.NUMBERING_SCHEMA_TYPE_GUIDS_2024 == P25.NUMBERING_SCHEMA_TYPE_GUIDS_2025


def test_every_2024_only_field_of_constructed_deltas_is_covered():
    """For each delta class genesis constructs, every 2024-only field is
    either hooked or its 2024 blank default is the corpus value."""
    hooked = {f for (_c, f) in P24.HOOKS_2024}
    blank_ok = {
        "m_scheduleInstanceIds",   # DBViewDrafting: [] on all 8 rst specimens
    }
    for cls in ("GeomTable", "RbsWireType", "RbsWireSettingsElem", "NumberingSchema",
                "BrowserOrganization", "ModelGraphicsStyle", "ViewDisplayMgr",
                "ReinforcementSettings", "VertCompoundStructureGStep",
                "AutoCamSettingsElem", "RbsDuctSettingsElem", "MEPNetworkTracker",
                "RbsDistributionSysType", "DBViewDrafting", "DBView3d",
                "DBViewPlan", "Viewport", "BrowserOrganizationTracking"):
        d = P24.diff_class(cls)
        for x in d.get("deltas", []):
            for f in (x.get("only_2024") or []):
                assert f in hooked or f in blank_ok, f"{cls}.{f} not covered"


def test_class_id_2024_matches_version_model_anchors():
    from rvt import versions
    anchors = versions.KNOWN_RELEASES[2024].anchors
    for name in ("ElementHeader", "GElement", "SerializedDummy", "GStyleElem",
                 "CategoryElem", "Level", "ADocument", "Element"):
        assert P24.class_id_2024(name) == anchors[name], name


def test_frozen_table_exists_and_agrees():
    tab = P24.portability_table(write=True)
    assert tab["counts"].get("MISSING-2024", 0) >= 13
    assert tab["counts"].get("LAYOUT-DELTA", 0) >= 40
    assert tab["counts"].get("VERSION-ONLY", 0) >= 3
    assert os.path.exists(P24.PORTABILITY_JSON)
    nm = tab["non_monotonic_findings"]
    assert "GeomStep" in nm["deltas_that_differ_from_2025"]
    assert "DBViewDrafting" in nm["deltas_that_differ_from_2025"]
    assert set(nm["missing_2024_but_present_2025"]) == {
        "SheetCollection", "SheetsInSheetCollectionTracker", "MEPNetworkDataElem",
        "STEPExportSettings", "BuildingOperatingYearSchedule"}
    assert "AutoCamSettingsElem" in nm["delta_only_in_2024"]


# ---------------------------------------------------------------------------
# 2. adapt(): field maps + round-trip gate
# ---------------------------------------------------------------------------
def test_adapt_wall_type_roundtrips_and_drops_geomstep_extras():
    rec = T.new_wall_type("PT Wall", [("structure", 200, INVALID)], elem_id=9200001)
    pr = P24.adapt_record(rec)
    assert pr.class_id == P24.class_id_2024("BasicWallType")
    v = P24.verify_ported(pr)
    assert v["ok"], v
    step = pr.obj["m_geomSteps"]["value"]["m_bRepFormGList"][0]["value"]
    # 2024: NO extra-data field under either name
    assert "m_oExtraData" not in step and "m_oExtraDatas" not in step


def test_adapt_fill_pattern_geomtable_gets_mined_defaults():
    rec = T.new_fill_pattern("PT Solid", [], elem_id=9200002)
    pr = P24.adapt_record(rec)
    gt = pr.obj["m_pGeomTable"]["value"]
    assert gt["m_maxSafeTag"] == -1
    assert gt["m_lastCheckedKingsUserModificationDate"] == -1
    assert P24.verify_ported(pr)["ok"]


def test_adapt_wire_type_writes_size_string():
    rec = T.new_wire_type("PT THWN", max_size_id=9200050, elem_id=9200003)
    pr = P24.adapt_record(rec, resolve_name=lambda i: "500" if i == 9200050 else None)
    assert pr.obj["m_strMaxConductorSize"] == "500"
    assert "m_idMaxConductorSize" not in pr.obj
    assert P24.verify_ported(pr)["ok"]
    pr2 = P24.adapt_record(T.new_wire_type("PT2", max_size_id=1, elem_id=9200004))
    assert pr2.obj["m_strMaxConductorSize"] == P24.WIRE_MAX_SIZE_FALLBACK_2024


def test_adapt_wire_settings_gets_mined_doubles():
    from rvt.genesis import settings as st
    pr = P24.adapt_record(st.wire_settings(elem_id=9200005))
    assert pr.obj["m_dMaxVoltageBranchSizing"] == 0.02
    assert pr.obj["m_dMaxVoltageFeederSizing"] == 0.03
    assert pr.obj["m_dAmbientTemperature"] == P24.WIRE_SETTINGS_2024["m_dAmbientTemperature"]
    assert P24.verify_ported(pr)["ok"]


def test_adapt_browser_organization_sort_param():
    from rvt.genesis import settings as st
    rec = st.browser_organization("all", sort_by=-1005112, elem_id=9200006)
    pr = P24.adapt_record(rec)
    assert pr.obj["m_sortParamId"] == -1005112
    assert "m_sortParameter" not in pr.obj
    assert P24.verify_ported(pr)["ok"]


def test_adapt_numbering_schema_matches_2024_oracle_shape():
    from rvt.genesis.residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    rec = builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], elem_id=9200007)
    pr = P24.adapt_record(rec)
    o = pr.obj
    assert o["schemaTypeGuid"]["m_value"] == \
        P24.NUMBERING_SCHEMA_TYPE_GUIDS_2024[-2009000]
    assert o["m_minimumNumberOfDigits"] == 1
    assert o["m_isMatchingEnabled"] is True
    pc = o["m_oPartitionDescriptionCreator"]
    assert pc["ptr_class"] == "ParameterBasedPartitionDescriptionCreator"
    assert pc["value"]["m_partitionParameterId"] == -1154614
    assert o["m_scopeCategories"] == [-2009000]
    assert P24.verify_ported(pr)["ok"]


def test_adapt_autocam_renames_and_retypes_the_camera_vectors():
    from rvt.genesis import settings as st
    pr = P24.adapt_record(st.auto_cam_settings(elem_id=9200008))
    o = pr.obj
    for new, old in P24.AUTOCAM_RENAMES_2024.items():
        assert new in o and old not in o, (new, old)
    assert o["m_sceneFront"] == [0.0, 1.0, 0.0]      # our scene frame carried
    assert o["m_sceneUp"] == [0.0, 0.0, 1.0]
    assert o["m_homeEye"] == [0.0, 0.0, 0.0]
    assert o["m_homeProjToPageScale"] == -1.0        # same-name carry
    assert P24.verify_ported(pr)["ok"]


def test_adapt_duct_settings_converts_dynamic_to_kinematic_viscosity():
    from rvt.genesis import settings as st
    rec = st.duct_settings(elem_id=9200009)
    mu, rho = rec.obj["m_airDynamicViscosity"], rec.obj["m_dAirDensity"]
    pr = P24.adapt_record(rec)
    assert pr.obj["m_dAirViscosity"] == mu / rho     # nu = mu / rho, exact
    assert "m_airDynamicViscosity" not in pr.obj
    assert pr.obj["m_dAirDensity"] == rho            # density carries as-is
    assert P24.verify_ported(pr)["ok"]


def test_adapt_mep_network_tracker_map_empty_carries_nonempty_refused():
    from rvt.genesis import settings as st
    pr = P24.adapt_record(st.tracker("MEPNetworkTracker", elem_id=9200010))
    assert pr.obj["m_component2BaseElementMap"] == []
    assert "m_component2BaseSegmentMap" not in pr.obj
    assert P24.verify_ported(pr)["ok"]
    bad = st.tracker("MEPNetworkTracker", elem_id=9200011,
                     overlay={"m_component2BaseSegmentMap": [{"first": 1, "second": 2}]})
    with pytest.raises(P24.PortabilityError):
        P24.adapt_record(bad)


def test_adapt_distribution_system_drops_high_leg_phase():
    rec = T.new_distribution_system("PT 480/277", elem_id=9200012)
    pr = P24.adapt_record(rec)
    assert "m_highLegPhase" not in pr.obj
    assert P24.verify_ported(pr)["ok"]


def test_adapt_hvac_day_schedule_survives_the_2024_field_reorder():
    """HVACLoadScheduleElem v4->3: same own fields, opposite order -- the
    target-chain walk reorders; values carry.  (Its Obj shape has no
    header/rep, so the class-level adapt is the vehicle.)"""
    from rvt.genesis.residue_a2 import hvac_day_schedule
    o = hvac_day_schedule("PT Always On", [1.0] * 24, elem_id=9200015, cells=None)
    a = P24.adapt("HVACLoadScheduleElem", o.value)
    assert a["m_strName"] == "PT Always On"
    assert a["m_24HourSchedules"] == [1.0] * 24
    v = P24.verify_roundtrip_2024(P24.class_id_2024("HVACLoadScheduleElem"), a)
    assert v["ok"], v
    # its year-schedule wrapper is one of the five 2024-absent classes
    with pytest.raises(P24.Missing2024):
        P24.adapt("BuildingOperatingYearSchedule", {})


def test_adapt_refuses_missing_2024_constructors():
    from rvt.genesis import settings as st
    with pytest.raises(P24.Missing2024):
        P24.adapt_record(T.new_conductor_size("12", 2.05, elem_id=9200013))
    for cls in ("SheetsInSheetCollectionTracker", "MEPNetworkDataElem",
                "STEPExportSettings"):
        with pytest.raises(P24.Missing2024):
            P24.adapt_record(st.tracker(cls, elem_id=9200014))


def test_regen_wildcard_classrefs_all_resolve_in_2024():
    """Settings headers carry regen-wildcard CLASSREFS; the walk refuses a
    classref with no 2024 twin.  The only wildcard naming a missing class
    (SheetCollection) lives inside SheetsInSheetCollectionTracker -- itself
    missing -- so no live constructor path hits the refusal.  Every other
    wildcard-carrying tracker adapts green, header included."""
    from rvt.genesis import settings as st
    from rvt.genesis.settings import REGEN_WILDCARDS
    for owner, cls_list in REGEN_WILDCARDS.items():
        for c in cls_list:
            if not P24.exists_2024(c):
                assert not P24.exists_2024(owner), \
                    f"{owner} exists in 2024 but its wildcard {c} does not"
    ids = T.IdSource(9_300_000)
    for build in (lambda: st.tracker("KeynoteTagsOnSheetsTracker", ids=ids),
                  lambda: st.tracker("AssemblyTracker", ids=ids),
                  lambda: st.tracker("MEPSystemTracker", ids=ids),
                  lambda: st.tracker("MEPComponentTracker", ids=ids),
                  lambda: st.tracker("LayoutNodesTracker", ids=ids),
                  lambda: st.tracker("RevisionCloudsOnSheetsTracker", ids=ids),
                  lambda: st.gcs_tracker(ids=ids)):
        rec = build()
        assert P24.verify_ported(P24.adapt_record(rec))["ok"], rec.class_name


def test_selftest_battery_green():
    rep = P24.selftest(verbose=False)
    assert rep["ok"], [r for r in rep["records"] if not r.get("ok", True)]
    assert all(r["refused"] for r in rep["refusals"])


# ---------------------------------------------------------------------------
# 3. sample-backed corpus-shape parity + specimen byte gate (skip off dev box)
# ---------------------------------------------------------------------------
@needs_sample
def test_adapted_shapes_match_2024_corpus():
    """Key-set parity: the adapted object's field keys must equal a decoded
    2024 sample record's keys for the same class."""
    from rvt import versions
    from rvt.mutate import Document
    with versions.reading(RST24):
        doc = Document.from_file(RST24)

    def sample_keys(cls):
        for eid in doc.et_by_id:
            if doc.class_of(eid) == cls:
                return set((doc.value(eid) or {}).keys())
        return None

    from rvt.genesis import settings as st
    pairs = [
        ("BasicWallType", P24.adapt_record(
            T.new_wall_type("PT", [("structure", 200, INVALID)], elem_id=9200020)).obj),
        ("RbsWireType", P24.adapt_record(
            T.new_wire_type("PT", elem_id=9200021)).obj),
        ("RbsWireSettingsElem", P24.adapt_record(
            st.wire_settings(elem_id=9200022)).obj),
        ("BrowserOrganization", P24.adapt_record(
            st.browser_organization("all", elem_id=9200023)).obj),
        ("AutoCamSettingsElem", P24.adapt_record(
            st.auto_cam_settings(elem_id=9200024)).obj),
        ("RbsDuctSettingsElem", P24.adapt_record(
            st.duct_settings(elem_id=9200025)).obj),
        ("MEPNetworkTracker", P24.adapt_record(
            st.tracker("MEPNetworkTracker", elem_id=9200026)).obj),
    ]
    from rvt.genesis.residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    pairs.append(("NumberingSchema", P24.adapt_record(
        builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], elem_id=9200027)).obj))
    for cls, ours in pairs:
        want = sample_keys(cls)
        if want is None:
            continue
        assert set(ours.keys()) == want, (cls, set(ours) ^ want)


@needs_sample
def test_specimen_byte_level_gate():
    """OUR adapted constructors byte-exact vs Autodesk's own 2024 records
    (auto-cam / MEP tracker / pen-table layout), plus specimen re-encode
    round-trips for every ported class."""
    rep = P24.verify_specimen_byte_level(verbose=False)
    assert rep["ok"], rep
    assert rep["AutoCamSettingsElem"]["byte_exact"]
    assert rep["MEPNetworkTracker"]["byte_exact"]
    assert rep["PenWidthTableElem"]["byte_exact"]
    rts = rep["specimen_roundtrips"]
    missing = [c for c, r in rts.items() if r == "no-specimen"]
    assert not missing, f"specimen list stale: {missing}"


@needs_sample
def test_mined_constants_still_hold_in_2024_corpus():
    from rvt import versions
    from rvt.mutate import Document
    with versions.reading(RST24):
        doc = Document.from_file(RST24)
    ws = next((doc.value(e) for e in doc.et_by_id
               if doc.class_of(e) == "RbsWireSettingsElem"), None)
    assert ws is not None
    assert ws["m_dMaxVoltageBranchSizing"] == 0.02
    assert ws["m_dMaxVoltageFeederSizing"] == 0.03
    assert ws["m_dAmbientTemperature"] == P24.WIRE_SETTINGS_2024["m_dAmbientTemperature"]
    rs = next((doc.value(e) for e in doc.et_by_id
               if doc.class_of(e) == "ReinforcementSettings"), None)
    assert rs is not None and rs["m_numberVaryingLengthRebarsIndividually"] is True
    ds = next((doc.value(e) for e in doc.et_by_id
               if doc.class_of(e) == "RbsDuctSettingsElem"), None)
    assert ds is not None
    assert ds["m_dAirViscosity"] == pytest.approx(1.6225337e-4, rel=1e-6)


@needs_sample
def test_duct_viscosity_rule_bit_exact_against_both_corpora():
    """The kinematic rule nu = mu / rho is Autodesk's own migration: the
    2026 rst duct settings' mu/rho equals the 2024 rst m_dAirViscosity
    BIT-exact (both files carry the same rho)."""
    from rvt import versions
    from rvt.mutate import Document
    rst26 = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
    if not os.path.exists(rst26):
        pytest.skip("2026 samples not present")
    doc26 = Document.from_file(rst26)
    v26 = next((doc26.value(e) for e in doc26.et_by_id
                if doc26.class_of(e) == "RbsDuctSettingsElem"), None)
    with versions.reading(RST24):
        doc24 = Document.from_file(RST24)
    v24 = next((doc24.value(e) for e in doc24.et_by_id
                if doc24.class_of(e) == "RbsDuctSettingsElem"), None)
    assert v26 and v24
    assert v26["m_dAirDensity"] == v24["m_dAirDensity"]
    assert v26["m_airDynamicViscosity"] / v26["m_dAirDensity"] == v24["m_dAirViscosity"]


# ---------------------------------------------------------------------------
# 4. the frozen 2024 miner artifacts
# ---------------------------------------------------------------------------
MINERS = os.path.join(ROOT, "experiments", "genesis2024", "miners")
needs_miners = pytest.mark.skipif(
    not os.path.exists(os.path.join(MINERS, "builtin_category_enum_2024.json")),
    reason="2024 miners not frozen here")


@needs_miners
def test_frozen_miners_are_coherent():
    with open(P24.ENUM_2024_JSON) as fh:
        enum = json.load(fh)
    assert enum["release"] == 2024
    assert enum["count"] == len(enum["categories"]) > 1000
    assert enum["cuttable"] == sum(1 for c in enum["categories"] if c["cut"])
    with open(P24.PROFILE_2024_JSON) as fh:
        prof = json.load(fh)
    assert prof["release"] == 2024 and prof["count"] == len(prof["keys"])
    # the four flag-word keys that differ from the 2026 profile carry the
    # 2024 value (same finding as 2025: 0x400200e -> 0x400201e)
    for k in ("-2000710:1", "-2000711:1", "-2000712:1", "-2000713:1"):
        assert prof["keys"][k]["ab"] == 0x400201E, k
    with open(P24.PEN_2024_JSON) as fh:
        pen = json.load(fh)
    assert pen["scale_breakpoints"] == [10, 20, 50, 100, 200, 500]
    assert pen["pens_per_vector"] == 16
    assert all(r["perspective_scale"] == -1 and r["draft_scale"] == -1
               for r in pen["project_tables"])
    with open(P24.PALETTE_2024_JSON) as fh:
        pal = json.load(fh)
    assert pal["laws_hold"] is True
    assert pal["element_id_set"] == {"present_empty": pal["property_sets"]}
    assert set(pal["param_containers_ascending"]) == {"True"}
    assert set(pal["param_ids_negative"]) == {"True"}


@needs_miners
def test_frozen_pen_constants_match_the_2026_constructor_constants():
    """The pen-table format constants port value-unchanged: the 2026
    constructor's breakpoints/count ARE the 2024 corpus values."""
    from rvt.genesis.settings import PEN_COUNT, PEN_SCALE_BREAKPOINTS
    assert P24.PEN_SCALE_BREAKPOINTS_2024 == list(PEN_SCALE_BREAKPOINTS)
    assert P24.PEN_COUNT_2024 == PEN_COUNT

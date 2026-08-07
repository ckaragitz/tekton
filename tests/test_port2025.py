"""tests/test_port2025.py -- the genesis-2025 constructor portability layer.

Proves (1) the CONFIRMED portability verdicts (including the four
layout-delta classes the plan's table missed), (2) the field-map hooks,
(3) the adapt() transform round-trips byte-exact under the 2025 schema and
matches the 2025 corpus field shape, (4) the conductor catalog is refused
honestly.  Sample-backed assertions skip cleanly off the dev machine.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import port2025 as P25                              # noqa: E402
from rvt.genesis import types as T                                   # noqa: E402
from rvt.genesis.types import INVALID                                # noqa: E402

RST25 = os.path.join(ROOT, "samples", "2025", "rstbasicsampleproject.rvt")
needs_sample = pytest.mark.skipif(not os.path.exists(RST25),
                                  reason="quarantined 2025 samples not present")


# ---------------------------------------------------------------------------
# 1. the CONFIRMED portability verdicts
# ---------------------------------------------------------------------------
def test_conductor_catalog_missing_2025():
    for cls in ("CustomElement", "NamingCell", "RbsConductorMaterial",
                "RbsConductorTemperatureRating", "RbsConductorInsulationMaterial",
                "RbsConductorSize"):
        assert P25.diff_class(cls)["verdict"] == "MISSING-2025", cls
        assert not P25.exists_2025(cls)


def test_machinery_layer_identical():
    # the plan's section-1 claim, re-proven: the document machinery ports as-is
    for cls in ("ADocument", "Element", "Symbol", "ElementHeader", "GElement",
                "SerializedDummy", "ElemTable", "ElemRec", "DocumentHistory",
                "DocumentIncrementTable", "PartitionTable"):
        assert P25.diff_class(cls)["verdict"] == "IDENTICAL", cls


def test_planned_layout_deltas_confirmed():
    for cls in ("GeomTable", "RbsWireType", "RbsWireSettingsElem",
                "RbsWireSizesElem", "NumberingSchema", "BrowserOrganization",
                "ModelGraphicsStyle", "ViewDisplayMgr", "AssemblyCodeTable",
                "KeynoteTable", "StructSettingsElem", "ReinforcementSettings",
                "VertCompoundStructureGStep", "DatumPlaneGeomStep",
                "CoordinateElemBaseGeomStep", "MakeCutterForPlanRegionsGStep",
                "ViewerGStep"):
        assert P25.diff_class(cls)["verdict"] == "LAYOUT-DELTA", cls


def test_deltas_the_plan_missed_are_real():
    """The verification's headline finding: four layout deltas the plan's
    section-5a table did not list -- all in classes genesis constructs."""
    d = P25.diff_class("DBView")
    assert d["verdict"] == "LAYOUT-DELTA"
    assert any("m_viewPositionId" in (x.get("only_2026") or []) for x in d["deltas"])
    for sub in ("DBView3d", "DBViewPlan", "DBViewProject", "DBViewDrafting",
                "RbsDbViewSystemNavigator"):
        assert P25.diff_class(sub)["verdict"] == "LAYOUT-DELTA", sub
    d = P25.diff_class("DBViewDrafting")
    assert any("m_sheetTitleBlockId" in (x.get("only_2026") or []) for x in d["deltas"])
    d = P25.diff_class("Viewport")
    assert d["version_2026"] == 13 and d["version_2025"] == 10
    only = [f for x in d["deltas"] for f in (x.get("only_2026") or [])]
    assert set(only) >= {"m_viewPosition", "m_viewAnchor"}
    d = P25.diff_class("BrowserOrganizationTracking")
    only25 = [f for x in d["deltas"] for f in (x.get("only_2025") or [])]
    assert set(only25) >= {"m_currentBrOrgViews", "m_currentBrOrgSheets",
                           "m_currentBrOrgSchedules"}


def test_every_2025_only_field_of_constructed_deltas_is_covered():
    """For each delta class genesis constructs, every 2025-only field is
    either hooked or its 2025 blank default is the corpus value (bool False /
    empty).  A new 2025-only field appearing un-hooked must fail here."""
    hooked = {f for (_c, f) in P25.HOOKS}
    blank_ok = set()                     # 2025-only fields whose blank IS corpus
    for cls in ("GeomTable", "RbsWireType", "RbsWireSettingsElem", "NumberingSchema",
                "BrowserOrganization", "ModelGraphicsStyle", "ViewDisplayMgr",
                "ReinforcementSettings", "VertCompoundStructureGStep"):
        d = P25.diff_class(cls)
        for x in d.get("deltas", []):
            for f in (x.get("only_2025") or []):
                assert f in hooked or f in blank_ok, f"{cls}.{f} not covered"


def test_class_id_2025_matches_version_model_anchors():
    from rvt import versions
    anchors = versions.KNOWN_RELEASES[2025].anchors
    for name in ("ElementHeader", "GElement", "SerializedDummy", "GStyleElem",
                 "CategoryElem", "Level", "ADocument", "Element"):
        assert P25.class_id_2025(name) == anchors[name], name


def test_frozen_table_exists_and_agrees():
    tab = P25.portability_table(write=True)
    assert tab["counts"].get("MISSING-2025", 0) >= 6
    assert tab["counts"].get("LAYOUT-DELTA", 0) >= 17
    assert os.path.exists(P25.PORTABILITY_JSON)


# ---------------------------------------------------------------------------
# 2. adapt(): field maps + round-trip gate
# ---------------------------------------------------------------------------
def test_adapt_wall_type_roundtrips_and_renames_geomstep():
    rec = T.new_wall_type("PT Wall", [("structure", 200, INVALID)], elem_id=9100001)
    pr = P25.adapt_record(rec)
    assert pr.class_id == P25.class_id_2025("BasicWallType")
    v = P25.verify_ported(pr)
    assert v["ok"], v
    step = pr.obj["m_geomSteps"]["value"]["m_bRepFormGList"][0]["value"]
    assert "m_oExtraData" in step and "m_oExtraDatas" not in step


def test_adapt_fill_pattern_geomtable_gets_mined_defaults():
    rec = T.new_fill_pattern("PT Solid", [], elem_id=9100002)
    pr = P25.adapt_record(rec)
    gt = pr.obj["m_pGeomTable"]["value"]
    assert gt["m_maxSafeTag"] == -1
    assert gt["m_lastCheckedKingsUserModificationDate"] == -1
    assert P25.verify_ported(pr)["ok"]


def test_adapt_wire_type_writes_size_string():
    rec = T.new_wire_type("PT THWN", max_size_id=9100050, elem_id=9100003)
    pr = P25.adapt_record(rec, resolve_name=lambda i: "500" if i == 9100050 else None)
    assert pr.obj["m_strMaxConductorSize"] == "500"
    assert "m_idMaxConductorSize" not in pr.obj
    assert P25.verify_ported(pr)["ok"]
    # unresolvable falls back to the mined sample label, with a note
    pr2 = P25.adapt_record(T.new_wire_type("PT2", max_size_id=1, elem_id=9100004))
    assert pr2.obj["m_strMaxConductorSize"] == P25.WIRE_MAX_SIZE_FALLBACK_2025


def test_adapt_wire_settings_gets_mined_doubles():
    from rvt.genesis import settings as st
    pr = P25.adapt_record(st.wire_settings(elem_id=9100005))
    assert pr.obj["m_dMaxVoltageBranchSizing"] == 0.02
    assert pr.obj["m_dMaxVoltageFeederSizing"] == 0.03
    assert pr.obj["m_dAmbientTemperature"] == P25.WIRE_SETTINGS_2025["m_dAmbientTemperature"]
    assert P25.verify_ported(pr)["ok"]


def test_adapt_browser_organization_sort_param():
    from rvt.genesis import settings as st
    rec = st.browser_organization("all", sort_by=-1005112, elem_id=9100006)
    pr = P25.adapt_record(rec)
    assert pr.obj["m_sortParamId"] == -1005112
    assert "m_sortParameter" not in pr.obj
    assert P25.verify_ported(pr)["ok"]


def test_adapt_numbering_schema_matches_2025_oracle_shape():
    from rvt.genesis.residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    rec = builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], elem_id=9100007)
    pr = P25.adapt_record(rec)
    o = pr.obj
    assert o["schemaTypeGuid"]["m_value"] == \
        P25.NUMBERING_SCHEMA_TYPE_GUIDS_2025[-2009000]
    assert o["m_minimumNumberOfDigits"] == 1
    assert o["m_isMatchingEnabled"] is True
    pc = o["m_oPartitionDescriptionCreator"]
    assert pc["ptr_class"] == "ParameterBasedPartitionDescriptionCreator"
    assert pc["value"]["m_partitionParameterId"] == -1154614
    assert o["m_scopeCategories"] == [-2009000]
    assert P25.verify_ported(pr)["ok"]


def test_adapt_refuses_conductor_catalog():
    rec = T.new_conductor_size("12", 2.05, elem_id=9100008)
    with pytest.raises(P25.Missing2025):
        P25.adapt_record(rec)


def test_selftest_battery_green():
    rep = P25.selftest(verbose=False)
    assert rep["ok"], [r for r in rep["records"] if not r.get("ok", True)]


# ---------------------------------------------------------------------------
# 3. sample-backed corpus-shape parity (skip off the dev machine)
# ---------------------------------------------------------------------------
@needs_sample
def test_adapted_shapes_match_2025_corpus():
    """Key-set parity: the adapted object's field keys must equal a decoded
    2025 sample record's keys for the same class (the corpus is the shape
    oracle; VALUES stay ours)."""
    from rvt import versions
    from rvt.mutate import Document
    with versions.reading(RST25):
        doc = Document.from_file(RST25)

    def sample_keys(cls):
        for eid in doc.et_by_id:
            if doc.class_of(eid) == cls:
                return set((doc.value(eid) or {}).keys())
        return None

    from rvt.genesis import settings as st
    pairs = [
        ("BasicWallType", P25.adapt_record(
            T.new_wall_type("PT", [("structure", 200, INVALID)], elem_id=9100020)).obj),
        ("RbsWireType", P25.adapt_record(
            T.new_wire_type("PT", elem_id=9100021)).obj),
        ("RbsWireSettingsElem", P25.adapt_record(
            st.wire_settings(elem_id=9100022)).obj),
        ("BrowserOrganization", P25.adapt_record(
            st.browser_organization("all", elem_id=9100023)).obj),
    ]
    from rvt.genesis.residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    pairs.append(("NumberingSchema", P25.adapt_record(
        builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], elem_id=9100024)).obj))
    for cls, ours in pairs:
        want = sample_keys(cls)
        if want is None:
            continue
        assert set(ours.keys()) == want, (cls, set(ours) ^ want)


# ---------------------------------------------------------------------------
# 4. the STAGED Y2025 ladder (guards the artifacts the orchestrator uploads;
#    skip when the ladder has not been built on this machine)
# ---------------------------------------------------------------------------
SUBST_DIR = os.path.join(ROOT, "experiments", "genesis2025", "subst")
PROBES = os.path.join(SUBST_DIR, "probes.json")
needs_ladder = pytest.mark.skipif(not os.path.exists(PROBES),
                                  reason="Y2025 ladder not staged here")


@needs_ladder
def test_staged_ladder_is_honest_and_valid():
    import json
    with open(PROBES) as fh:
        m = json.load(fh)
    assert m.get("release") == 2025
    assert "PENDING" in (m.get("viewer_certification") or "")
    assert "PENDING" in ((m.get("base_2025") or {}).get("certification") or "")
    ctrl = (m.get("standing_control") or {}).get("file") or ""
    assert ctrl and os.path.exists(os.path.join(ROOT, ctrl))
    for name in ("Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9", "Y_cat"):
        rp = os.path.join(SUBST_DIR, f"{name}.json")
        assert os.path.exists(rp), f"{name} report missing"
        with open(rp) as fh:
            rep = json.load(fh)
        assert rep.get("verdict") == "VALID", (name, rep.get("verdict"),
                                               rep.get("FAILED_SELF_CHECK"))
        v = rep.get("validator") or {}
        assert v.get("ok") and v.get("errors") == 0, (name, v)
        bd = rep.get("byte_delta") or {}
        assert bd.get("assertion_holds"), (name, bd.get("problems"))
        assert bd.get("adocument_identical") and bd.get("elemtable_identical"), name
        assert os.path.exists(os.path.join(SUBST_DIR, f"{name}.rvt")), name
    yn = os.path.join(SUBST_DIR, "Yn.json")
    assert os.path.exists(yn)


@needs_ladder
def test_staged_ladder_records_port2025_adaptation():
    import json
    for name in ("Y1", "Y6", "Y9"):
        with open(os.path.join(SUBST_DIR, f"{name}.json")) as fh:
            rep = json.load(fh)
        assert any("port2025" in n for n in (rep.get("build_notes") or [])), name


@needs_sample
def test_mined_constants_still_hold_in_corpus():
    from rvt import versions
    from rvt.mutate import Document
    with versions.reading(RST25):
        doc = Document.from_file(RST25)
    ws = next((doc.value(e) for e in doc.et_by_id
               if doc.class_of(e) == "RbsWireSettingsElem"), None)
    assert ws is not None
    assert ws["m_dMaxVoltageBranchSizing"] == 0.02
    assert ws["m_dMaxVoltageFeederSizing"] == 0.03
    assert ws["m_dAmbientTemperature"] == P25.WIRE_SETTINGS_2025["m_dAmbientTemperature"]
    rs = next((doc.value(e) for e in doc.et_by_id
               if doc.class_of(e) == "ReinforcementSettings"), None)
    assert rs is not None and rs["m_numberVaryingLengthRebarsIndividually"] is True

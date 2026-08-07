"""tests for rvt.famload_fix (the product-path fix layer) + the
loaded-content validator rule -- instbug-fix stream.

Pure-python law tests always run; file-backed tests skip cleanly when the
experiment artifacts / bases are not on disk (stream-local rule).
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import famload_fix as FX                                  # noqa: E402

FIX_DIR = os.path.join(ROOT, "experiments", "instbug", "fix")
G_ABPD = os.path.join(ROOT, "experiments", "genesis", "subst_k4",
                      "compose", "G_ABPD.rvt")
DEMO_OLD = os.path.join(ROOT, "experiments", "frontdoor", "demo-250v",
                        "prompt_room.rvt")
WF_NOFIX = os.path.join(ROOT, "experiments", "render", "g12", "WF_nofix.rvt")


def _need(path):
    if not os.path.isfile(path):
        pytest.skip(f"artifact not on disk: {os.path.relpath(path, ROOT)}")
    return path


# ---------------------------------------------------------------------------
# the corpus-law builders
# ---------------------------------------------------------------------------

def test_electrical_connector_cell_is_the_canonical_15_row_table():
    con = {"index": 1, "voltage": 2238.89, "poles": 3, "load": 100.0,
           "power_factor": 0.95}
    cell = FX.electrical_connector_cell(con, bindings=[{"first": -1140002,
                                                        "second": 123}],
                                        load_class_host=456)
    v = cell["value"]
    rows = v["m_oRelevantParams"]["value"]["m_params"]
    assert cell["ptr_class"] == "ConnectorDataCell"
    assert [r["m_paramId"] for r in rows] == list(FX.EE_CELL_PARAM_ORDER)
    by = {r["m_paramId"]: r for r in rows}
    assert by[-1140002]["m_value"] == pytest.approx(2238.89)   # voltage
    assert by[-1140001]["m_int"] == 3                          # poles
    assert by[-1140018]["m_int"] == 31                         # 3-pole enum
    assert by[-1140008]["m_value"] == pytest.approx(0.95)      # power factor
    assert by[-1140014]["m_elemId"] == 456                     # load class elem
    assert by[-1140005]["m_value"] == pytest.approx(100.0)     # apparent load
    # corpus constants
    assert by[-1133412]["m_int"] == 1 and by[-1140009]["m_int"] == 1
    # every row carries the full corpus row shape
    for r in rows:
        assert set(r) == {"m_str", "m_oExpression", "m_value", "m_elemId",
                          "m_paramId", "m_int", "m_instance", "m_reporting"}
    assert v["m_propId2FamParamIdBindings"] == [{"first": -1140002, "second": 123}]
    assert v["m_domain"] == 2 and v["m_connectorType"] == 1


def test_single_pole_cell_uses_the_30_enum():
    cell = FX.electrical_connector_cell({"index": 1, "poles": 1},
                                        bindings=[], load_class_host=-1)
    by = {r["m_paramId"]: r for r in cell["value"]["m_oRelevantParams"]["value"]["m_params"]}
    assert by[-1140018]["m_int"] == 30
    assert by[-1140014]["m_elemId"] == -1


def test_lawful_manager_class():
    m = FX.lawful_instance_connector_manager([{"ptr_class": "Connector",
                                               "pid": -1, "value": {}}])
    assert m["ptr_class"] == "FamilyInstanceConnectorManager"
    assert set(m["value"]) == {"m_setDeletedConnectors", "m_connPtrArray",
                               "m_modifiers"}


def test_sort_content_recset_orders_by_guid_bytes_le():
    gs = [str(uuid.uuid4()) for _ in range(6)]
    lv = {"m_oContentTable": {"value": {"m_ContentRecSet": [
        {"m_ContentKey": {"m_guidKey": g}} for g in gs]}}}
    assert not FX.recset_sorted(lv) or len(set(gs)) < 2
    n = FX.sort_content_recset(lv)
    assert n == 6
    assert FX.recset_sorted(lv)
    got = [r["m_ContentKey"]["m_guidKey"]
           for r in lv["m_oContentTable"]["value"]["m_ContentRecSet"]]
    assert got == sorted(gs, key=lambda g: uuid.UUID(g).bytes_le)


def test_sort_is_idempotent_and_safe_on_empty():
    lv = {"m_oContentTable": {"value": {"m_ContentRecSet": []}}}
    assert FX.sort_content_recset(lv) == 0
    assert FX.recset_sorted(lv)


# ---------------------------------------------------------------------------
# the patch context
# ---------------------------------------------------------------------------

def test_fixed_product_path_patches_and_reverts():
    from rvt.famgen import loader as L
    before = (L.register_in_host_adocument, L.author_host_family,
              L.author_family_symbol, L.author_family_instance,
              L._connector_data_cells)
    with FX.fixed_product_path():
        after = (L.register_in_host_adocument, L.author_host_family,
                 L.author_family_symbol, L.author_family_instance,
                 L._connector_data_cells)
        assert all(a is not b for a, b in zip(after, before))
    restored = (L.register_in_host_adocument, L.author_host_family,
                L.author_family_symbol, L.author_family_instance,
                L._connector_data_cells)
    assert all(a is b for a, b in zip(restored, before))


def test_patched_registration_sorts_content_table():
    from rvt.famgen import loader as L

    class Plan:                        # the minimal duck for register_
        guid = str(uuid.uuid4())
        surrogate_id = 999
        symbol_id = 1000
        instance_id = -1
        episode = 1

    lv = {"m_oContentTable": {"value": {"m_ContentRecSet": [
        {"m_ContentKey": {"m_guidKey": "ffffffff-ffff-4fff-8fff-ffffffffffff"},
         "m_author": "x", "m_history": {}, "m_EpisodeCounts": []}]}},
        "m_pAppInfoManager": {"value": {"m_appInfoArr": [
            {"ptr_class": "FamilyMgr", "pid": -1,
             "value": {"m_arrLoadedFamilyInfo": []}}]}}}
    Plan.guid = "00000000-0000-4000-8000-000000000001"      # sorts FIRST
    with FX.fixed_product_path():
        rep = L.register_in_host_adocument(lv, Plan, category=-2001040,
                                           unit_records=41)
    assert rep.get("content_table_sorted") is True
    assert FX.recset_sorted(lv)
    first = lv["m_oContentTable"]["value"]["m_ContentRecSet"][0]
    assert first["m_ContentKey"]["m_guidKey"] == Plan.guid


# ---------------------------------------------------------------------------
# emitted artifacts (skip when not built)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,ef,ei", [("BXfix_f1i1", 1, 1),
                                        ("BXfix_f6i6", 6, 6),
                                        ("DEMO_250v_room_v2", 6, 6)])
def test_emitted_fix_probes_hold_every_fix_assertion(name, ef, ei):
    p = _need(os.path.join(FIX_DIR, f"{name}.rvt"))
    rep = FX.assert_fixed(p, expect_families=ef, expect_instances=ei)
    assert rep["ok"], rep
    assert rep["content_table_sorted"]
    assert not rep["instances_unlawful_manager"]
    assert not rep["families_null_famdim"]
    assert not rep["symbols_null_moverestr"]
    assert not rep["connector_cells_below_corpus_floor"]
    assert not rep["instances_without_phase"]
    assert rep["census"]["coherent"] is True


# ---------------------------------------------------------------------------
# the loaded-content validator rule
# ---------------------------------------------------------------------------

def test_validator_rule_detects_the_failing_demo():
    p = _need(DEMO_OLD)
    from rvt.validate import validate_file
    r = validate_file(p)
    lc = [f for f in r.errors if "loaded-content" in f.where]
    msgs = " | ".join(f.message for f in lc)
    assert lc, "the loaded-content rule must flag the audit-failed demo"
    assert "connector manager" in msgs
    assert "NOT ascending" in msgs


def test_validator_rule_clean_on_certified_files():
    from rvt.validate import validate_file
    for p in (G_ABPD, WF_NOFIX):
        if not os.path.isfile(p):
            continue
        r = validate_file(p)
        lc_err = [f for f in r.errors if "loaded-content" in f.where]
        assert not lc_err, (p, [f.message for f in lc_err])
        assert len(r.errors) == 0


def test_validator_rule_clean_on_fixed_demo():
    p = _need(os.path.join(FIX_DIR, "DEMO_250v_room_v2.rvt"))
    from rvt.validate import validate_file
    r = validate_file(p)
    assert len(r.errors) == 0, [f"{f.where}: {f.message}" for f in r.errors[:4]]
    lc_warn = [f for f in r.warnings if "loaded-content" in f.where]
    assert not lc_warn, [f.message for f in lc_warn]

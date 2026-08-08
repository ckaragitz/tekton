"""Tests for rvt.genesis.residue_a2 -- the Group-A round-2 residue
constructors (the REMAINING UNSUBSTITUTED CLASSES of the first round's
disposition list) + the in-place ZC-rungs (ZC_hvac / ZC_elec / ZC_conduit /
ZC_systype / ZC_analysis / ZC_browse / ZC_deep) built on the CERTIFIED
ZA_deep.

Fast tests exercise the constructors, the claim contract, our data and the
frozen enums; the integration tests need ``experiments/genesis/subst_k4/
residue_a/ZA_deep.rvt`` (the certified parent) and are skipped without it.
"""
from __future__ import annotations

import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt.genesis import residue_a2 as R2                      # noqa: E402
from rvt.genesis import residue_a as RA                        # noqa: E402
from rvt.genesis.types import INVALID                          # noqa: E402

ZA_DEEP = R2.DEFAULT_PARENT
HAS_BASE = os.path.exists(ZA_DEEP) and os.path.exists(R2.DEFAULT_PARENT_REPORT)
RESIDUE_DIR = R2.RESIDUE_DIR
P_INT = R2.P_INT


# ===========================================================================
# 1. the claim contract
# ===========================================================================
#: the residue disposition list of docs/inbox/genesis-residue-A.md (the
#: classes the first Group-A round did not reach) -- THIS stream's charter
DISPOSITION_LIST = {
    "HVACLoadSpaceTypeElem", "HVACLoadBuildingTypeElem", "HVACLoadScheduleElem",
    "BuildingOperatingYearSchedule", "ElectricalDemandFactorDefinition",
    "ElectricalLoadClassification", "ConduitStandardType", "ConduitSizesElem",
    "CableTraySizesElem", "BasicWallType", "FloorAttributes", "FabricSheetType",
    "FabricWireType", "AreaReportSettingsElem", "AreaSchemePlanTopologies", "AreaTypeElem",
    "AssemblyCodeTable", "ColorFillSchema", "LoadCaseElem", "LoadNatureElem", "DataStorage",
    "BrowserOrganization", "DBDrawing", "DBViewDrafting",
}


def test_rung_order_and_planners_agree():
    assert set(R2.RUNG_ORDER) == set(R2.PLANNERS) == set(R2.CLAIMED_CLASSES)


def test_claimed_classes_cover_the_disposition_list_exactly():
    claimed = {c for cs in R2.CLAIMED_CLASSES.values() for c in cs}
    stated = {k.split("(")[0] for k in R2.NON_INPLACE}
    # every disposition-list class is either claimed (in-place rung) or stated
    covered = claimed | stated
    missing = DISPOSITION_LIST - covered
    assert not missing, f"disposition-list classes with neither a rung nor a stated operation: {missing}"
    # claimed classes are all disposition-list classes (no class from another stream)
    assert claimed <= DISPOSITION_LIST


def test_non_inplace_operations_are_stated():
    assert set(R2.NON_INPLACE) == {"RvtLinkSymbol", "RvtLinkInstance", "DataStorage",
                                    "AreaSchemePlanTopologies(room)"}
    for k, (op, why) in R2.NON_INPLACE.items():
        assert op.startswith("DELETE"), f"{k}: the operation must be a deletion form"
        assert len(why) > 80, "every non-in-place item carries an honest reason"


def test_reached_elsewhere_covers_group_b_and_the_other_group_a_buckets():
    r = R2.REACHED_ELSEWHERE
    for c in ("RbsWireInsulationType", "PipeSegment", "MaterialElem", "ParamElemExternal",
              "RefPlane", "SketchPlane", "CategoryElem", "Family", "CurveElem"):
        assert c in r, f"{c} must be attributed to its owning stream"
    # never claim a class another stream owns
    claimed = {c for cs in R2.CLAIMED_CLASSES.values() for c in cs}
    assert not (claimed & set(r)), f"claimed classes owned elsewhere: {claimed & set(r)}"


# ===========================================================================
# 2. the frozen enums (interface constants)
# ===========================================================================

def test_hvac_type_enums_frozen_and_dense():
    enums = R2.load_hvac_type_enums()
    sp = {int(k): v for k, v in enums["space_types"].items()}
    bt = {int(k): v for k, v in enums["building_types"].items()}
    assert len(sp) == 125 and sorted(sp) == list(range(125))
    assert len(bt) == 33 and sorted(bt) == list(range(33))
    # the canonical names are non-empty (the identity we keep)
    assert all(v for v in sp.values()) and all(v for v in bt.values())
    # a few well-known members of the public space-type list
    assert sp[92].startswith("Office - Enclosed")
    assert sp[104] == "Plenum"
    assert bt[18] == "Office"


def test_our_profile_maps_cover_every_enum_key():
    enums = R2.load_hvac_type_enums()
    for k in enums["space_types"]:
        assert int(k) in R2.SPACE_TYPE_PROFILE, f"space type {k} has no profile of ours"
        assert R2.SPACE_TYPE_PROFILE[int(k)] in R2.SPACE_PROFILES
    for k in enums["building_types"]:
        assert int(k) in R2.BUILDING_TYPE_PROFILE, f"building type {k} has no profile of ours"
        assert R2.BUILDING_TYPE_PROFILE[int(k)] in R2.BUILDING_PROFILES


def test_our_profiles_reference_our_schedule_library():
    keys = {s["key"] for s in R2.DAY_SCHEDULES}
    for name, p in R2.SPACE_PROFILES.items():
        for role in ("occ_sched", "ltg_sched", "pwr_sched"):
            assert p[role] in keys, f"space profile {name}.{role} = {p[role]} not in our schedule library"
    for name, p in R2.BUILDING_PROFILES.items():
        for role in ("occ_sched", "ltg_sched", "pwr_sched"):
            assert p[role] in keys, f"building profile {name}.{role} not in our schedule library"


def test_day_schedules_are_ours_and_well_formed():
    assert len(R2.DAY_SCHEDULES) >= 25
    seen = set()
    for s in R2.DAY_SCHEDULES:
        assert s["name"].startswith(R2.PREFIX + " ")
        assert s["key"] not in seen
        seen.add(s["key"])
        assert len(s["hours"]) == 24
        assert all(0.0 <= x <= 1.0 for x in s["hours"])
    # the always-on / always-off / half references exist for role fallbacks
    assert {"on24", "off", "half24"} <= seen


# ===========================================================================
# 3. the pure constructors
# ===========================================================================

def test_demo_all_constructors_roundtrip():
    assert R2.demo() == 0


def _ok(o):
    rep = RA.check_object(o.class_name, o.value)
    assert rep["ok"], f"{o.class_name}: {rep}"
    return rep


def test_day_schedule_constructor():
    o = R2.hvac_day_schedule(R2.gen("Test Schedule"), [1.0] * 24, elem_id=7)
    _ok(o)
    assert o.value["m_strName"] == R2.gen("Test Schedule")
    assert o.value["m_24HourSchedules"] == [1.0] * 24
    with pytest.raises(ValueError):
        R2.hvac_day_schedule("x", [1.0] * 23)


def test_day_schedule_keeps_slot_cells_verbatim():
    # a slot with a NULL cell list stays null in place (the machinery is the slot's)
    o = R2.hvac_day_schedule("x", [0.0] * 24, elem_id=1, cells=None)
    assert o.value["m_cellList"] is None
    o2 = R2.hvac_day_schedule("x", [0.0] * 24, elem_id=1)
    assert o2.value["m_cellList"] is not None                    # no slot -> the standard helper


def test_space_type_constructor_keeps_identity_and_applies_our_values():
    prof = R2.SPACE_PROFILES["office_enclosed"]
    o = R2.hvac_space_type(92, "Office - Enclosed", prof, occ_year=11, ltg_year=12,
                           pwr_year=13, elem_id=5)
    _ok(o)
    v = o.value
    assert v["m_eSpaceType"] == 92 and v["m_name"] == "Office - Enclosed"    # interface identity kept
    assert v["m_LightingLoadDensity"] == pytest.approx(prof["lpd"] * P_INT)
    assert v["m_PowerLoadDensity"] == pytest.approx(prof["epd"] * P_INT)
    assert v["m_dAreaPerPerson"] == prof["ft2_per_person"]
    assert v["m_coolingSetPoint"] == pytest.approx((prof["clg_f"] - 32) * 5 / 9 + 273.15)
    assert v["m_heatingSetPoint"] == pytest.approx((prof["htg_f"] - 32) * 5 / 9 + 273.15)
    assert (v["m_idOccupancySchedule"], v["m_idLightingSchedule"], v["m_idPowerSchedule"]) == (11, 12, 13)
    assert v["m_isPlenum"] is False
    # our declared value fields
    for f in ("m_LightingLoadDensity", "m_coolingSetPoint", "m_idOccupancySchedule"):
        assert f in o.ours


def test_space_type_plenum_profile_is_a_true_plenum():
    o = R2.hvac_space_type(104, "Plenum", R2.SPACE_PROFILES["plenum"],
                           occ_year=1, ltg_year=1, pwr_year=1, elem_id=5)
    _ok(o)
    assert o.value["m_isPlenum"] is True
    assert o.value["m_LightingLoadDensity"] == 0.0 and o.value["m_dAreaPerPerson"] == 0.0


def test_unoccupied_profiles_have_no_occupants():
    for k in ("corridor", "stair", "mech_elec", "parking", "plenum", "storage_inactive"):
        assert R2.SPACE_PROFILES[k]["ft2_per_person"] is None
        o = R2.hvac_space_type(0, "x", R2.SPACE_PROFILES[k], occ_year=1, ltg_year=1,
                               pwr_year=1, elem_id=1)
        assert o.value["m_dAreaPerPerson"] == 0.0


def test_building_type_constructor():
    prof = R2.BUILDING_PROFILES["office"]
    o = R2.hvac_building_type(18, "Office", prof, occ_year=2, ltg_year=3, pwr_year=4, elem_id=6)
    _ok(o)
    v = o.value
    assert v["m_eBuildingType"] == 18 and v["m_name"] == "Office"
    assert v["m_strEquipmentStartTime"] == prof["eq_start"]
    assert v["m_strEquipmentEndTime"] == prof["eq_end"]
    assert v["m_dCoolingSetPoint"] == pytest.approx((prof["unocc_clg_f"] - 32) * 5 / 9 + 273.15)


def test_year_schedule_is_reproduced_byte_identical():
    slot = {"m_id": 9, "m_daySchedules": [5] * 365, "m_cellList": None}
    o = R2.hvac_year_schedule_reproduced(slot)
    assert o.value == slot and o.value is not slot
    assert o.ours == []


def test_demand_factor_rules_are_our_nec_library():
    for key in ("continuous125", "receptacle", "motor", "kitchen", "no_diversity"):
        assert key in R2.DEMAND_RULES
    for key in R2.DEMAND_EXTRAS:
        assert key in R2.DEMAND_RULES
    o = R2.our_demand_factor("receptacle", elem_id=7, cells=None)
    _ok(o)
    v = o.value
    assert v["m_ruleType"] == R2.RULE_LOAD
    assert len(v["m_values"]) == 2                      # 10 kVA breakpoint (NEC 220.44)
    assert v["m_values"][0]["m_factor"] == 1.0 and v["m_values"][1]["m_factor"] == 0.5
    assert v["m_values"][0]["m_maxRange"] == pytest.approx(10000.0 * P_INT)
    assert v["m_cellList"] is None                      # slot cells kept verbatim
    # rule codes used are only the corpus-verified ones (0 constant / 3 count / 4 load)
    for spec in R2.DEMAND_RULES.values():
        assert spec["rule"] in (0, 3, 4), spec["name"]


def test_load_classification_keeps_wiring_and_role():
    slot = {"m_id": 9, "m_demandFactorId": 700, "m_signitureType": 1,
            "m_estLoadParamElemId": 71, "m_estCurrentParamElemId": 72,
            "m_actualSpaceLoadParamElemId": 73, "m_demandFactorParamElemId": 74,
            "m_totalCurrentParamElemId": 75, "m_totalLoadParamElemId": 76,
            "m_cellList": None, "m_designOptionId": -1}
    motor = next(e for e in R2.LOAD_CLASS_LIBRARY if e["role"] == "motor")
    o = R2.our_load_classification(motor, slot)
    _ok(o)
    v = o.value
    assert v["m_name"] == motor["name"] and v["m_signitureType"] == 1
    assert v["m_demandFactorId"] == 700                   # demand wiring kept
    assert (v["m_estLoadParamElemId"], v["m_estCurrentParamElemId"], v["m_actualSpaceLoadParamElemId"],
            v["m_demandFactorParamElemId"], v["m_totalCurrentParamElemId"],
            v["m_totalLoadParamElemId"]) == (71, 72, 73, 74, 75, 76)   # 6 companion ids kept
    # our label phrasing (house standard), the reader's %1!s! token retained
    assert v["m_actualElectricalLoadLabel"] == "%1!s! - Actual Load"
    assert all("%1!s!" in v[k] for k in ("m_panelConnectedLabel", "m_panelEstimatedLabel"))


def test_load_class_library_has_exactly_the_three_reserved_roles():
    roles = [e["role"] for e in R2.LOAD_CLASS_LIBRARY if e["role"]]
    assert sorted(roles) == ["motor", "other", "spare"]
    sig = {e["role"]: e["signature"] for e in R2.LOAD_CLASS_LIBRARY if e["role"]}
    assert sig == {"motor": 1, "other": 2, "spare": 3}
    for e in R2.LOAD_CLASS_LIBRARY:
        assert e["name"].startswith(R2.PREFIX + " ")
        assert e["rule"] in R2.DEMAND_RULES
        assert e["space_class"] in (0, 1, 2)


def test_empty_assembly_code_table():
    o = R2.our_empty_assembly_code_table({"m_id": 12})
    _ok(o)
    v = o.value
    ents = v["m_oKeyBasedTreeEntries"]["value"]
    assert ents["m_keyBasedTreeEntrySet"] == [] and ents["m_orphans"] == []
    cells = v["m_cellList"]["value"]["m_cells"]
    assert cells[0]["ptr_class"] == "ExternalFileReferenceCell" and cells[0]["value"] == {}
    assert cells[1]["value"] == {"m_externalResourceReferences": [],
                                 "m_externalResourceReferencesExpanded": []}
    assert v["m_hasUserCustomizedAssemblyCode"] is False


def test_conduit_standards_and_sizes():
    keys = [s["key"] for s in R2.OUR_CONDUIT_STANDARDS]
    assert keys[:4] == ["emt", "imc", "rmc", "pvc40"] and "pvc80" in keys
    o = R2.our_conduit_standard(R2.OUR_CONDUIT_STANDARDS[0], {"m_id": 15})
    _ok(o)
    assert o.value["m_symbolInfo"]["value"]["m_name"] == R2.OUR_CONDUIT_STANDARDS[0]["name"]
    sizes = R2.our_conduit_sizes({"emt": 15, "pvc80": 16}, {"m_id": 17, "m_cellList": None})
    _ok(sizes)
    pairs = sizes.value["m_sizes"]
    assert {p["first"] for p in pairs} == {15, 16}
    for p in pairs:
        rows = p["second"]["m_sizeData"]
        assert len(rows) >= 10
        for r in rows:
            assert 0 < r["m_dInnerDiameter"] < r["m_dOuterDiameter"]
            assert r["m_dSize"] > 0 and r["m_dBendRadius"] > 0


def test_cable_tray_sizes_are_nema_widths():
    o = R2.our_cable_tray_sizes({"m_id": 3, "m_cellList": None})
    _ok(o)
    rows = o.value["m_sizes"]["m_sizeData"]
    from rvt.genesis import house_standard as hs
    assert [round(r["m_dSize"] * 12.0, 3) for r in rows] == list(hs.CABLE_TRAY_WIDTHS_IN)


def test_load_nature_and_case():
    n = R2.our_load_nature(R2.gen("Dead (D)"), {"m_id": 10, "m_cellList": None})
    _ok(n)
    assert n.value["m_name"] == R2.gen("Dead (D)")
    assert n.value["m_pParamValueSetAString"]["value"]["m_paramSet"][0] == {
        "m_paramId": R2.BIP_LOAD_NATURE_NAME, "m_value": R2.gen("Dead (D)")}
    c = R2.our_load_case(R2.gen("D-1"), 3, {"m_id": 11, "m_categoryId": R2.OST_LoadCasesLive,
                                            "m_natureId": 10, "m_cellList": None})
    _ok(c)
    assert c.value["m_number"] == 3 and c.value["m_categoryId"] == R2.OST_LoadCasesLive
    assert c.value["m_natureId"] == 10                     # nature wiring kept
    # every load-case category has our nature + case names
    for cat in R2.LOAD_CASE_ORDER:
        assert cat in R2.LOAD_NATURE_BY_CATEGORY and cat in R2.LOAD_CASE_BY_CATEGORY
        assert R2.LOAD_NATURE_BY_CATEGORY[cat].startswith(R2.PREFIX + " ")


def test_fabric_wire_and_sheet():
    w = R2.our_fabric_wire_type({"m_id": 13, "m_cellList": None})
    _ok(w)
    assert w.value["m_symbolInfo"]["value"]["m_name"] == R2.FABRIC_WIRE["name"]
    d_ft = R2.FABRIC_WIRE["diameter_in"] / 12.0
    assert w.value["m_wireDiameter"] == pytest.approx(d_ft)
    assert w.value["m_bendDiameter"] == pytest.approx(d_ft * R2.FABRIC_WIRE["bend_diameter_factor"])
    s = R2.our_fabric_sheet_type({"m_id": 14, "m_sheetMaterial": 999, "m_cellList": None}, 13)
    _ok(s)
    v = s.value
    assert v["m_majorDirectionWireType"] == 13 == v["m_minorDirectionWireType"]
    assert v["m_sheetMaterial"] == 999                     # material slot wiring kept
    assert v["m_overallLength"] == R2.FABRIC_SHEET["overall_length_ft"]
    assert v["m_userEnteredSheetMass"] == R2.FABRIC_SHEET["mass_kg"]
    assert v["m_majorNumberOfWires"] > 1 and v["m_minorNumberOfWires"] > 1


def test_color_fill_schema_entries_by_role():
    # department scheme on rooms: our department vocabulary entries
    slot = {"m_id": 1, "m_categoryId": -2000160, "m_paramId": -1006907, "m_bByRange": False,
            "m_areaSchemeId": -1, "m_strName": "Department", "m_title": "Department Legend",
            "m_colorFillArr": [], "m_cellList": None}
    o = R2.our_color_fill_schema(dict(slot), 0)
    v = o.value
    assert v["m_strName"] == R2.gen("Rooms by Department")
    assert len(v["m_colorFillArr"]) == len(R2.DEPARTMENT_VOCABULARY)
    vals = [e["m_paramStorage"]["m_str"]["m_str"] for e in v["m_colorFillArr"]]
    assert vals == list(R2.DEPARTMENT_VOCABULARY)
    # by-range area scheme: our breakpoints
    slot2 = dict(slot, m_categoryId=-2000160, m_paramId=-1006902, m_bByRange=True)
    o2 = R2.our_color_fill_schema(slot2, 1)
    assert len(o2.value["m_colorFillArr"]) == len(R2.AREA_RANGES_FT2)
    assert all(e["m_bByRange"] for e in o2.value["m_colorFillArr"])
    # room NAME scheme: left empty (auto-populate) -- registration pairing kept
    slot3 = dict(slot, m_paramId=-1006900)
    o3 = R2.our_color_fill_schema(slot3, 2)
    assert o3.value["m_colorFillArr"] == []
    assert o3.value["m_categoryId"] == -2000160 and o3.value["m_paramId"] == -1006900


def test_sheet_view_overlay_empties_link_overrides_and_sets_our_identity():
    slot = {
        "m_viewName": "Framing Plans", "m_sheetNumber": "S101", "m_date": "02/03/15",
        "m_issueDate": "02/03/15", "m_drawnBy": "Author", "m_checkedBy": "Checker",
        "m_designedBy": "Designer", "m_approvedBy": "Approver", "m_dbDrawingId": 55,
        "m_pRvtLinkOverrides": {"ptr_class": "RvtLinkOverrides", "pid": -1, "value": {
            "m_invisibleSet": [1], "m_halftoneSet": [2], "m_underlaySet": [3],
            "m_displaySettingsMap": [{"first": 1250029, "second": {}}],
            "m_upgradeForWorksetVisibilityInLinkFiles": True}},
    }
    o = R2.our_sheet_view(copy.deepcopy(slot))
    v = o.value
    assert v["m_viewName"] == R2.SHEET_IDENTITY["view_name"]
    assert v["m_sheetNumber"] == R2.SHEET_IDENTITY["sheet_number"]
    for f in ("m_drawnBy", "m_checkedBy", "m_designedBy", "m_approvedBy"):
        assert v[f] == "GEN"
    lo = v["m_pRvtLinkOverrides"]["value"]
    assert lo["m_displaySettingsMap"] == []                # the link-symbol pin removed
    assert lo["m_invisibleSet"] == [] and lo["m_halftoneSet"] == [] and lo["m_underlaySet"] == []
    assert v["m_dbDrawingId"] == 55                        # drawing wiring kept
    assert lo["m_upgradeForWorksetVisibilityInLinkFiles"] is True   # machinery kept


def test_area_report_overlay_sets_our_text_only():
    slot = {"m_allSettings": [{"m_name": "x", "m_prefixArcSector": "S", "m_prefixTriangle": "T",
                               "m_fontAnotName": "Whatever", "m_fontTagName": "Whatever",
                               "m_fontSize": [0.1, 0.1], "m_idCategory": [9, 8], "m_idFont": [7, 6],
                               "m_unitmachine": {"deep": [1, 2, 3]}}],
            "m_id": 3, "m_cellList": None}
    o = R2.our_area_report_settings(slot)
    st = o.value["m_allSettings"][0]
    assert st["m_prefixArcSector"] == R2.AREA_REPORT_SETTINGS["prefix_arc_sector"]
    assert st["m_fontAnotName"] == st["m_fontTagName"]
    assert st["m_idCategory"] == [9, 8] and st["m_idFont"] == [7, 6]      # own wiring kept
    assert st["m_unitmachine"] == {"deep": [1, 2, 3]}                    # machinery kept


def test_reproduced_slot_is_identical_and_declares_nothing_ours():
    slot = {"m_id": 4, "m_areaSchemeId": 9490, "m_eSpaceType": 2, "m_cellList": {"x": []}}
    o = R2.reproduced("AreaTypeElem", slot, "test")
    assert o.value == slot and o.value is not slot and o.ours == []


def test_browser_organization_specs_are_ours_and_typed():
    names = [s["name"] for s in R2.BROWSER_ORGANIZATIONS_EXTRA]
    assert len(names) == 5 == len(set(names))
    assert all(n.startswith(R2.PREFIX + " ") for n in names)
    assert {s["type"] for s in R2.BROWSER_ORGANIZATIONS_EXTRA} == {"views", "sheets"}
    o = R2.our_browser_organization(R2.BROWSER_ORGANIZATIONS_EXTRA[0],
                                    {"m_id": 5, "m_type": 0, "m_cellList": None})
    _ok(o)
    assert o.value["m_type"] == 0
    assert o.value["m_symbolInfo"]["value"]["m_name"] == R2.BROWSER_ORGANIZATIONS_EXTRA[0]["name"]


# ===========================================================================
# 4. the electrical assignment logic (deterministic web planning)
# ===========================================================================

class _Doc:
    """Minimal doc double: value(id) over a dict."""

    def __init__(self, values):
        self._v = values

    def value(self, e):
        return self._v.get(int(e))


def test_electrical_layer_roles_and_shared_demand_groups():
    values = {
        1: {"m_id": 1, "m_signitureType": 2, "m_demandFactorId": 100},   # other role
        2: {"m_id": 2, "m_signitureType": 1, "m_demandFactorId": 101},   # motor role
        3: {"m_id": 3, "m_signitureType": 3, "m_demandFactorId": 102},   # spare role
        4: {"m_id": 4, "m_signitureType": 0, "m_demandFactorId": 103},   # \
        5: {"m_id": 5, "m_signitureType": 0, "m_demandFactorId": 103},   #  } share 103
        6: {"m_id": 6, "m_signitureType": 0, "m_demandFactorId": 103},   # /
        7: {"m_id": 7, "m_signitureType": 0, "m_demandFactorId": 104},   # single
        100: {"m_id": 100}, 101: {"m_id": 101}, 102: {"m_id": 102}, 103: {"m_id": 103},
        104: {"m_id": 104}, 105: {"m_id": 105},                            # 105 unreferenced
    }
    doc = _Doc(values)
    plans, rep = R2.plan_electrical_layer(doc, [1, 2, 3, 4, 5, 6, 7],
                                           [100, 101, 102, 103, 104, 105])
    assert set(plans) == {1, 2, 3, 4, 5, 6, 7, 100, 101, 102, 103, 104, 105}
    # reserved roles by signature
    assert plans[1].value["m_signitureType"] == 2 and rep["roles"]["other"] == 1
    assert plans[2].value["m_signitureType"] == 1 and rep["roles"]["motor"] == 2
    assert plans[3].value["m_signitureType"] == 3 and rep["roles"]["spare"] == 3
    # the 3 classifications sharing demand 103 share ONE rule of ours
    rules = {rep["assignment"][str(c)]["rule"] for c in (4, 5, 6)}
    assert len(rules) == 1
    assert rep["demand_rules"]["103"]["our_rule"] == rules.pop()
    # the unreferenced demand slot 105 got one of our extras
    assert rep["demand_rules"]["105"]["our_rule"] in R2.DEMAND_EXTRAS
    assert any(d["demand_slot"] == 105 for d in rep["unreferenced_demand"])
    # every demand plan's rule matches the report; wiring kept on classes
    for c in (1, 2, 3, 4, 5, 6, 7):
        assert plans[c].value["m_demandFactorId"] == values[c]["m_demandFactorId"]
    # all objects round-trip
    for o in plans.values():
        _ok(o)


# ===========================================================================
# 5. integration on the CERTIFIED ZA_deep (skipped without the file)
# ===========================================================================

@pytest.fixture(scope="module")
def parent():
    if not HAS_BASE:
        pytest.skip("certified parent ZA_deep.rvt not present")
    return R2.Parent2(ZA_DEEP)


def test_parent_is_certified():
    if not HAS_BASE:
        pytest.skip("ZA_deep not present")
    V3 = RA._v3()
    assert V3.certification_of(ZA_DEEP) is not None, "the rung parent must be viewer-certified"


def test_residue_of_parent_matches_the_disposition_counts(parent):
    exp = {"HVACLoadSpaceTypeElem": 125, "HVACLoadBuildingTypeElem": 33,
           "HVACLoadScheduleElem": 27, "BuildingOperatingYearSchedule": 27,
           "ElectricalDemandFactorDefinition": 21, "ElectricalLoadClassification": 18,
           "ConduitStandardType": 5, "ConduitSizesElem": 1, "CableTraySizesElem": 1,
           "BasicWallType": 1, "FloorAttributes": 1, "FabricSheetType": 1, "FabricWireType": 1,
           "AreaReportSettingsElem": 1, "AreaSchemePlanTopologies": 6, "AreaTypeElem": 8,
           "AssemblyCodeTable": 1, "ColorFillSchema": 10, "LoadCaseElem": 8, "LoadNatureElem": 8,
           "DataStorage": 1, "BrowserOrganization": 5, "DBViewDrafting": 1, "DBDrawing": 1,
           "RvtLinkSymbol": 1, "RvtLinkInstance": 1}
    for cls, n in exp.items():
        assert len(parent.residue_of(cls)) == n, cls
    # no claimed slot is one the ladder already landed
    for cls in exp:
        for s in parent.residue_of(cls):
            assert s not in parent.landed


def test_plan_hvac_covers_the_web_and_keeps_identity(parent):
    plan = R2.plan_hvac(parent)
    bc = plan.by_class
    assert bc == {"HVACLoadSpaceTypeElem": 125, "HVACLoadBuildingTypeElem": 33,
                  "HVACLoadScheduleElem": 27, "BuildingOperatingYearSchedule": 27}
    for slot, o in plan.plans.items():
        assert slot not in parent.landed
        old = parent.value(slot)
        if o.class_name == "HVACLoadSpaceTypeElem":
            # interface identity kept exactly; profile from our map
            assert o.value["m_eSpaceType"] == old["m_eSpaceType"]
            assert o.value["m_name"] == old["m_name"]
            assert R2.SPACE_TYPE_PROFILE[old["m_eSpaceType"]] in R2.SPACE_PROFILES
            # schedule references point at (residue) year-schedule slots
            for f in ("m_idOccupancySchedule", "m_idLightingSchedule", "m_idPowerSchedule"):
                assert parent.cls_of.get(o.value[f]) == "BuildingOperatingYearSchedule"
        elif o.class_name == "HVACLoadBuildingTypeElem":
            assert o.value["m_eBuildingType"] == old["m_eBuildingType"]
            assert o.value["m_name"] == old["m_name"]
        elif o.class_name == "BuildingOperatingYearSchedule":
            assert o.value == old                          # reproduced byte-identical
        elif o.class_name == "HVACLoadScheduleElem":
            assert o.value["m_strName"].startswith(R2.PREFIX + " ")
            assert len(o.value["m_24HourSchedules"]) == 24
        RA.check_object(o.class_name, o.value)


def test_plan_hvac_year_slot_map_uses_all_our_day_profiles(parent):
    plan = R2.plan_hvac(parent)
    used = plan.info["day_library_used"]
    # our library's distinct profiles at the day slots
    assert len(set(used)) == len(used) == len(parent.residue_of("HVACLoadScheduleElem"))


def test_plan_elec_on_the_base(parent):
    plan = R2.plan_elec(parent)
    assert plan.by_class == {"ElectricalDemandFactorDefinition": 21, "ElectricalLoadClassification": 18}
    rep = plan.info
    assert set(rep["roles"]) == {"motor", "other", "spare"}
    # every classification keeps its demand + companion wiring
    for slot, o in plan.plans.items():
        if o.class_name != "ElectricalLoadClassification":
            continue
        old = parent.value(slot)
        assert o.value["m_demandFactorId"] == old["m_demandFactorId"]
        for f in ("m_estLoadParamElemId", "m_estCurrentParamElemId", "m_actualSpaceLoadParamElemId",
                  "m_demandFactorParamElemId", "m_totalCurrentParamElemId", "m_totalLoadParamElemId"):
            assert o.value[f] == old[f]
        # our name
        assert o.value["m_name"].startswith(R2.PREFIX + " ")
    # the role slots keep their signature types
    for role, slot in rep["roles"].items():
        assert plan.plans[slot].value["m_signitureType"] == {"motor": 1, "other": 2, "spare": 3}[role]
    # a demand slot shared by several classifications serves ONE rule
    for g in rep["groups"]:
        if g["size"] > 1:
            rules = {rep["assignment"][str(c)]["rule"] for c in g["class_slots"]}
            assert len(rules) == 1, f"shared demand slot {g['demand_slot']} serves mixed rules"


def test_plan_analysis_reproduces_machinery_and_leaves_the_room_topology(parent):
    plan = R2.plan_analysis(parent)
    left = plan.residue_left
    assert "AreaSchemePlanTopologies(room)" in left and left["AreaSchemePlanTopologies(room)"] == [9744]
    assert "DataStorage(vendor ES blob)" in left
    for slot, o in plan.plans.items():
        old = parent.value(slot)
        if o.class_name in ("AreaTypeElem", "AreaSchemePlanTopologies"):
            assert o.value == old and o.ours == []       # reproduced byte-identical
        if o.class_name == "AreaSchemePlanTopologies":
            assert not (((old.get("m_pSet") or {}).get("value") or {}).get("m_set")), \
                "only EMPTY topology holders are reproduced -- the room's is left"
        if o.class_name == "AssemblyCodeTable":
            ents = o.value["m_oKeyBasedTreeEntries"]["value"]
            assert ents["m_keyBasedTreeEntrySet"] == []    # the UniFormat table is EMPTIED
        if o.class_name == "LoadCaseElem":
            assert o.value["m_categoryId"] == old["m_categoryId"]     # category enum kept
            assert o.value["m_natureId"] == old["m_natureId"]         # nature wiring kept


def test_plan_browse_adopts_the_sheet_and_leaves_the_link(parent):
    plan = R2.plan_browse(parent)
    assert plan.by_class == {"BrowserOrganization": 5, "DBViewDrafting": 1, "DBDrawing": 1}
    assert "RvtLinkSymbol(external link)" in plan.residue_left
    assert "RvtLinkInstance(external link)" in plan.residue_left
    dv = [o for o in plan.plans.values() if o.class_name == "DBViewDrafting"][0]
    assert dv.value["m_viewName"] == R2.SHEET_IDENTITY["view_name"]
    assert dv.value["m_pRvtLinkOverrides"]["value"]["m_displaySettingsMap"] == []
    dd = [o for o in plan.plans.values() if o.class_name == "DBDrawing"][0]
    assert dd.ours == []                                   # the drawing is reproduced


def test_merge_plans_has_no_collisions_and_no_protected_slot(parent):
    plans = [R2.PLANNERS[n](parent) for n in R2.RUNG_ORDER]
    deep = R2.merge_plans(plans)
    assert deep.name == "ZC_deep"
    assert len(deep.plans) == sum(len(p.plans) for p in plans)   # disjoint
    for slot in deep.plans:
        assert slot not in parent.landed, f"slot {slot} is already OURS -- never re-land"
        assert slot in parent.doc.et_by_id


# ===========================================================================
# 6. an end-to-end single rung (temp dir) -- the in-place law asserted
# ===========================================================================

def test_end_to_end_ZC_conduit_in_tempdir(parent, tmp_path):
    plan = R2.plan_conduit(parent)
    rep = RA.emit_rung(plan, parent, str(tmp_path), base_certification=None, control=None)
    assert rep["verdict"] == "VALID", rep.get("problems")
    bd = rep["byte_delta"]
    assert bd["assertion_holds"] and bd["only_partition_differs"]
    assert bd["elemtable_identical"] and bd["adocument_identical"]
    assert bd["records_changed_count"] == len(plan.plans)   # all 7 catalog slots carry our values
    assert (rep["validator"] or {}).get("errors") == 0
    assert (rep["structural"] or {}).get("ok")
    assert (rep["coherence"] or {}).get("coherent")
    assert rep["new_object_reference_check"]["dangling"] == 0
    assert set(rep["field_delta_by_class"]) == {"ConduitStandardType", "ConduitSizesElem",
                                                  "CableTraySizesElem"}


# ===========================================================================
# 7. the committed batch (skipped if the ladder was not run)
# ===========================================================================
COMMITTED = os.path.join(RESIDUE_DIR, "probes.json")
HAS_BATCH = os.path.exists(COMMITTED)


def test_committed_probes_manifest_bisection_first():
    if not HAS_BATCH:
        pytest.skip("committed batch not present (run: python -m rvt.genesis.residue_a2)")
    with open(COMMITTED) as fh:
        man = json.load(fh)
    order = man["upload_order_bisection_first"]
    assert order[0] == "ZC_deep"
    assert set(order) == {"ZC_deep", *R2.RUNG_ORDER}
    for e in man["probes"]:
        assert e["base"]["file"].endswith("residue_a/ZA_deep.rvt")
        assert e["verdict"] == "VALID", e["rung"]
        assert e["byte_delta"]["assertion_holds"] and e["byte_delta"]["only_partition_differs"]
        assert e["validator"]["errors"] == 0
    assert set(man["not_in_place_able_with_operation"]) == set(R2.NON_INPLACE)


def test_committed_reports_valid_and_control_matches_base():
    if not HAS_BATCH:
        pytest.skip("committed batch not present")
    import hashlib
    for name in ["ZC_deep"] + R2.RUNG_ORDER:
        p = os.path.join(RESIDUE_DIR, f"{name}.json")
        assert os.path.exists(p), f"missing report {name}"
        with open(p) as fh:
            rep = json.load(fh)
        assert rep["verdict"] == "VALID", (name, rep.get("problems"))
        assert rep["byte_delta"]["assertion_holds"]
        assert (rep["validator"] or {}).get("errors") == 0
        assert rep["new_object_reference_check"]["dangling"] == 0
    # the standing control is byte-identical to the certified base (the
    # .rvt binaries are git-ignored: absent on a fresh clone -> skip)
    ctrl = os.path.join(RESIDUE_DIR, "CTRL_ZA_deep_base.rvt")
    if not (os.path.exists(ctrl) or os.path.exists(ZA_DEEP)):
        pytest.skip("control binaries are git-ignored and absent (fresh clone)")
    assert os.path.exists(ctrl)
    def md5(p):
        with open(p, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()
    assert md5(ctrl) == md5(ZA_DEEP)


def test_committed_ZC_deep_field_delta_covers_the_claimed_classes():
    if not HAS_BATCH:
        pytest.skip("committed batch not present")
    with open(os.path.join(RESIDUE_DIR, "ZC_deep.json")) as fh:
        rep = json.load(fh)
    landed = {r["class"] for r in rep["landed_slots"]}
    claimed = {c for cs in R2.CLAIMED_CLASSES.values() for c in cs}
    assert claimed == landed, f"claimed vs landed: {claimed ^ landed}"
    # the reproduced-machinery classes are landed but byte-identical (0 delta)
    fd = rep["field_delta_by_class"]
    for cls in ("AreaTypeElem", "AreaSchemePlanTopologies", "BuildingOperatingYearSchedule",
                "DBDrawing"):
        assert cls not in fd, f"{cls} was declared reproduced but its fields differ"
    # the in-place law: no unexpected changed / added / removed records
    bd = rep["byte_delta"]
    assert bd["unexpected_changed_ids"] == [] or bd["unexpected_changed_ids"] is None
    assert not bd.get("records_added_ids") and not bd.get("records_removed_ids")


def test_committed_residue_after_ZC_deep_has_only_honest_leftovers():
    p = os.path.join(RESIDUE_DIR, "residue_after_ZC_deep.json")
    if not os.path.exists(p):
        pytest.skip("residue census not present")
    with open(p) as fh:
        zn = json.load(fh)
    for cls, row in zn["residue_by_class"].items():
        d = row["disposition"]
        assert not d.startswith("SHOULD BE OURS"), f"{cls}: {row['count']} slots we planned to land are still Autodesk's"
        assert d.startswith("other stream") or d.startswith("NOT in-place-able"), (cls, d)
    keys = set(zn["totals_by_disposition"])
    assert keys <= {"other stream", "NOT in-place-able"}
    assert zn["totals_by_disposition"].get("NOT in-place-able") == 4   # link pair + DataStorage + topo 9744

"""Tests for rvt.genesis.residue_a -- the Group-A residue constructors +
the in-place Z-rungs (Z_subcat / Z_annot / Z_datum / Z_pattern / Z_asset /
ZA_deep) built on the CERTIFIED Y9.

Fast tests exercise the constructors, the claim contract and the pure
helpers; the integration tests need ``experiments/genesis/subst_k4/Y9.rvt``
(the certified parent) and are skipped without it.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from rvt.genesis import residue_a as RA                       # noqa: E402
from rvt.genesis.types import INVALID, mm                       # noqa: E402

Y9 = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "Y9.rvt")
HAS_Y9 = os.path.exists(Y9)
RESIDUE_DIR = RA.RESIDUE_DIR


# ---------------------------------------------------------------------------
# the claim contract (Group A / Group B split)
# ---------------------------------------------------------------------------

def test_claimed_classes_sort_A_to_L():
    for rung, classes in RA.CLAIMED_CLASSES.items():
        for c in classes:
            assert "A" <= c[0].upper() <= "L", f"{rung}: {c} is not an A..L class (Group B's)"


def test_group_b_classes_sort_M_to_Z():
    for c in RA.GROUP_B_CLASSES:
        assert "M" <= c[0].upper() <= "Z", f"{c} sorts A..L -- it would be Group A's"


def test_non_inplace_reasons_are_stated_for_A_to_L_classes():
    for c, why in RA.NON_INPLACE.items():
        assert "A" <= c[0].upper() <= "L"
        assert len(why) > 40, "every non-in-place class carries an honest reason"


def test_rung_order_and_planners_agree():
    assert set(RA.RUNG_ORDER) == set(RA.PLANNERS) == set(RA.CLAIMED_CLASSES)


# ---------------------------------------------------------------------------
# pure constructors + helpers
# ---------------------------------------------------------------------------

def test_demo_all_constructors_roundtrip():
    assert RA.demo() == 0


def test_subcategory_names_are_ours():
    n = RA.our_subcategory_name(RA.OST_Doors, 0)
    assert n.startswith(RA.PREFIX) and "Door" in n
    # beyond the vocabulary -> honest numbered fallback, still ours
    far = RA.our_subcategory_name(RA.OST_Doors, 40)
    assert far.startswith(RA.PREFIX) and "Subcategory" in far
    unknown = RA.fallback_subcategory_name(-2999999, 3)
    assert unknown.startswith(RA.PREFIX) and "03" in unknown


def test_secret_internal_name_grammar():
    a = RA.secret_internal_name("LinAngDimStyle")
    b = RA.secret_internal_name("LinAngDimStyle")
    c = RA.secret_internal_name("RadDimStyle")
    assert a == b != c                                   # deterministic per role
    assert a.startswith("SecretInternalLinAngDimStyle")
    tail = a[len("SecretInternalLinAngDimStyle"):]
    assert tail and tail.isalnum() and any(ch.isdigit() for ch in tail)


def test_field_delta_reports_only_differences():
    a = {"x": 1, "y": {"z": [1.0, 2.0], "w": "s"}}
    b = {"x": 1, "y": {"z": [1.0, 3.0], "w": "s"}}
    d = RA.field_delta(a, b)
    assert d == ["y.z.[1]"]
    assert RA.field_delta(a, a) == []


def test_new_grid_geometry_is_a_vertical_datum_plane():
    o = RA.new_grid("01", (0.0, 0.0), (100.0, 0.0), attr_id=42, elevation_ft=10.0, elem_id=7)
    surf = o.value["m_pSurface"]["value"]
    assert surf["m_origin"] == [50.0, 0.0, 10.0]           # midpoint of the line at the elevation
    assert surf["m_xVec"] == [1.0, 0.0, 0.0] and surf["m_yVec"] == [0.0, 0.0, 1.0]
    env = surf["m_Envelope"]["m_corners"]
    assert env[0][0] == pytest.approx(-50.0) and env[1][0] == pytest.approx(50.0)
    assert o.value["m_text"] == "01" and o.value["m_attrId"] == 42
    assert o.value["m_id"] == 7
    rep = RA.check_object("Grid", o.value)
    assert rep["ok"], rep


def test_grid_convention_names_are_zero_padded_numbers():
    assert RA.GRID_CONVENTION["names"][:3] == ["01", "02", "03"]


def test_generic_asset_profile_is_frozen_and_constructor_uses_our_values():
    prof = RA.load_generic_asset_profile()
    assert prof["generic_specimens"] >= 100
    names = {p["name"] for p in prof["properties"]}
    for req in ("UIName", "generic_diffuse", "generic_glossiness", "BaseSchema", "assettype"):
        assert req in names
    # the free properties carry NO frozen value
    for p in prof["properties"]:
        if p["name"] in RA.GENERIC_ASSET_OURS:
            assert not p["constant"] and p["value"] is None, p["name"]
    o = RA.generic_appearance_asset("GEN Appearance - Test Grey", (128, 128, 128), glossiness=0.3,
                                    profile=prof)
    props = {p["value"]["m_sName"]: p["value"]["m_value"]
             for p in o.value["m_pAppearanceAsset"]["value"]["m_Asset"]["m_aAProperties"]}
    assert props["UIName"] == "GEN Appearance - Test Grey"
    assert props["generic_diffuse"][:3] == pytest.approx([0.502, 0.502, 0.502], abs=0.002)
    assert props["generic_glossiness"] == pytest.approx(0.3)
    assert props["BaseSchema"] == "GenericSchema" and props["assettype"] == "materialappearance"
    assert RA.check_object("AppearanceAssetElem", o.value)["ok"]


def test_arrowhead_and_type_constructors_carry_our_values():
    ah = RA.arrowhead_type(RA.gen("Arrow Filled 20 Degree"), category_id=99, elem_id=5)
    assert ah.value["m_tickType"] == 8 and ah.value["m_arrowFilled"] == 1
    assert ah.value["m_categoryId"] == 99
    gh = RA.grid_head_type("GEN Grid Head", font_id=1, line_category_id=2,
                           leader_category_id=INVALID, center_segment_category_id=INVALID)
    assert gh.value["m_bubbleAtEnd1"] is True and gh.value["m_bubbleAtEnd2"] is True
    assert gh.value["m_familyTagId"] == INVALID                      # family-free base
    ie = RA.interior_elevation_type("GEN Elevation", font_id=1, line_category_id=2)
    assert ie.value["m_shape"] == 1 and ie.value["m_orderedSubIndices"] == []
    assert ie.value["m_width"] == pytest.approx(mm(10.0))
    ct = RA.callout_head_type("GEN Callout", corner_radius_mm=2.0)
    assert ct.value["m_cornerRadius"] == pytest.approx(mm(2.0))
    f = RA.font_elem(9, size_mm=2.5)
    fv = f.value["m_pFont"]["value"]
    assert fv["m_name"] == RA.ANNOTATION_STANDARD["font"] and fv["m_size"] == pytest.approx(mm(2.5))
    assert fv["m_color"] == RA.FONT_COLOR_BLACK
    for o in (ah, gh, ie, ct, f):
        assert RA.check_object(o.class_name, o.value)["ok"], o.class_name


def test_inplace_category_and_gstyle_change_only_our_fields():
    # a synthetic slot shaped like a residue sub-category row
    slot_cat = {
        "m_pCategory": {"ptr_class": "Category", "pid": -1,
                        "value": {"m_name": "Plan Swing", "m_parentCategoryId": RA.OST_Doors,
                                  "m_categoryType": 1, "m_flags": 0}},
        "m_gstyleIds": [123], "m_ownerId": -1, "m_famId": -1,
        "m_designOptionId": -4, "m_id": 122, "m_cellList": None,
    }
    from rvt.genesis.types import blank_object, element_defaults
    base = blank_object("CategoryElem")
    element_defaults(base, 122, design_option=-4)
    base.update({k: v for k, v in slot_cat.items()})
    o = RA.inplace_category(base, "GEN Door - Swing (Plan)")
    delta = RA.field_delta(base, o.value)
    assert delta == ["m_pCategory.value.m_name"], delta
    assert o.value["m_pCategory"]["value"]["m_name"] == "GEN Door - Swing (Plan)"
    # gstyle row: only pen + colour differ
    slot_gs = blank_object("GStyleElem")
    element_defaults(slot_gs, 123, design_option=-4)
    slot_gs.update({
        "m_pGStyle": {"ptr_class": "GStyle", "pid": -1,
                      "value": {"m_linePatternId": RA.LINEPATTERN_SOLID, "m_materialElemId": -1,
                                "m_penNumber": 3, "m_color": 0xFF0000, "m_isScreenSized": False}},
        "m_categoryId": 122, "m_ownerId": -1, "m_gstyleType": 1, "m_famId": -1,
    })
    g = RA.inplace_gstyle(slot_gs, pen=1, color=0x181818)
    dg = RA.field_delta(slot_gs, g.value)
    assert set(dg) == {"m_pGStyle.value.m_penNumber", "m_pGStyle.value.m_color"}, dg


def test_level_vocabulary_and_appearance_palette_are_ours():
    assert all(isinstance(t[0], str) and isinstance(t[1], float) for t in RA.LEVEL_VOCABULARY)
    assert len(RA.APPEARANCE_PALETTE) >= 18                       # covers the 18 residue assets
    assert all(p["name"].startswith(RA.PREFIX) for p in RA.APPEARANCE_PALETTE)


# ---------------------------------------------------------------------------
# integration: plans against the certified Y9 (skipped without the file)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parent():
    if not HAS_Y9:
        pytest.skip("Y9.rvt (the certified parent) is not present")
    return RA.Parent(Y9)


def test_parent_residue_matches_the_Yn_census(parent):
    r = parent.residue
    # Yn: CategoryElem 209, GStyleElem 286, FontElem 35, DimensionStyle 12,
    # LeaderStyle 5, Grid 3, Level 7, FillPatternElem 4, LinePatternElem 3,
    # AppearanceAssetElem 18, DBViewType 72, Family 8, FamilySurrogate 8
    expect = {"CategoryElem": 209, "GStyleElem": 286, "FontElem": 35, "DimensionStyle": 12,
              "LeaderStyle": 5, "Grid": 3, "Level": 7, "FillPatternElem": 4, "LinePatternElem": 3,
              "AppearanceAssetElem": 18, "DBViewType": 72, "Family": 8, "FamilySurrogate": 8,
              "GridAttributes": 1, "InteriorElevAttributes": 9, "CalloutTag": 9,
              "LinearDimString": 1, "CurveElem": 5, "LegendComponent": 4, "LevelRoomPlan": 1}
    got = {k: len(r.get(k, [])) for k in expect}
    assert got == expect


def test_curtain_constellation_is_the_removal_set(parent):
    c = RA.curtain_constellation(parent.state)
    assert len(c["families"]) == 8
    assert c["by_class"]["Family"] == 8 and c["by_class"]["DBViewType"] == 72
    assert c["by_class"]["FamilySurrogate"] == 8
    assert c["count"] >= 220
    names = {f["name"] for f in c["families"]}
    assert "Rectangular Mullion" in names and "System Panel" in names


def test_every_planned_object_round_trips_and_plans_size_correctly(parent):
    sizes = {"Z_subcat": 415, "Z_annot": 23, "Z_datum": 10, "Z_pattern": 7, "Z_asset": 18}
    for name, planner in RA.PLANNERS.items():
        plan = planner(parent)
        assert len(plan.plans) == sizes[name], f"{name}: {len(plan.plans)} slots"
        fails = RA.selfcheck_plans(plan.plans)
        assert not fails, f"{name}: {fails[:3]}"


def test_subcat_plan_is_project_rows_only_and_names_are_ours(parent):
    plan = RA.plan_subcat(parent)
    by = plan.by_class
    assert by == {"GStyleElem": 246, "CategoryElem": 169}
    # every substituted named category carries OUR prefix; internal owned rows stay unnamed
    named = 0
    for slot, o in plan.plans.items():
        if o.class_name != "CategoryElem":
            continue
        nm = o.value["m_pCategory"]["value"]["m_name"]
        if nm:
            assert nm.startswith(RA.PREFIX), nm
            named += 1
    assert named >= 130
    # the family-scoped rows are left with a reason
    assert len(plan.residue_left["CategoryElem(family-scoped)"]) == 40
    assert len(plan.residue_left["GStyleElem(family-scoped)"]) == 40


def test_annot_plan_secret_styles_keep_role_and_symbols_are_family_free(parent):
    plan = RA.plan_annot(parent)
    roles = set()
    for slot, o in plan.plans.items():
        if o.class_name == "DimensionStyle":
            nm = o.value["m_symbolInfo"]["value"]["m_name"]
            assert nm.startswith("SecretInternal")
            roles.add(nm.split("DimStyle")[0])
        if o.class_name == "GridAttributes":
            assert o.value["m_familyTagId"] == INVALID
        if o.class_name == "InteriorElevAttributes":
            assert o.value["m_elevationSymbolId"] == INVALID
        if o.class_name == "CalloutTag":
            assert o.value["m_familyTagId"] == INVALID
    assert len(roles) == 4                                        # the four secret roles


def test_datum_plan_grids_ours_and_referenced_levels_keep_elevation(parent):
    plan = RA.plan_datum(parent)
    grids = [i for i in plan.info["grids"]]
    assert [g["our_name"] for g in grids] == ["01", "02", "03"]
    for lv in plan.info["levels"]:
        assert lv["our_name"].startswith(RA.PREFIX)
        if lv["referrers"]:
            assert lv["our_elevation_applied"] is False                # referenced datum keeps z


# ---------------------------------------------------------------------------
# integration: one end-to-end emission (the small pattern rung) + the reports
# ---------------------------------------------------------------------------

def test_z_pattern_end_to_end(parent, tmp_path):
    plan = RA.plan_pattern(parent)
    rep = RA.emit_rung(plan, parent, str(tmp_path))
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    bd = rep["byte_delta"]
    assert bd["assertion_holds"] and bd["only_partition_differs"]
    assert bd["elemtable_identical"] and bd["adocument_identical"]
    assert bd["records_added_ids"] == [] and bd["records_removed_ids"] == []
    assert rep["validator"]["ok"] and rep["validator"]["errors"] == 0
    assert rep["structural"]["ok"] and rep["coherence"]["coherent"]
    assert rep["new_object_reference_check"]["dangling"] == 0
    assert os.path.exists(os.path.join(str(tmp_path), "Z_pattern.rvt"))


@pytest.mark.parametrize("name", ["ZA_deep", "Z_subcat", "Z_annot", "Z_datum", "Z_pattern", "Z_asset"])
def test_built_ladder_reports_are_valid(name):
    p = os.path.join(RESIDUE_DIR, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{name} not built (run python -m rvt.genesis.residue_a)")
    with open(p) as fh:
        rep = json.load(fh)
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    bd = rep["byte_delta"]
    assert bd["assertion_holds"] and bd["adocument_identical"] and bd["elemtable_identical"]
    assert bd["records_added_ids"] == [] and bd["records_removed_ids"] == []
    assert rep["validator"]["ok"] and rep["validator"]["errors"] == 0
    assert rep["new_object_reference_check"]["dangling"] == 0


def test_probes_manifest_is_bisection_first():
    p = os.path.join(RESIDUE_DIR, "probes.json")
    if not os.path.exists(p):
        pytest.skip("probes.json not built (run python -m rvt.genesis.residue_a)")
    with open(p) as fh:
        m = json.load(fh)
    assert m["upload_order_bisection_first"][0] == "ZA_deep"
    assert m["standing_control"] and "control" in json.dumps(m["standing_control"]).lower()
    for e in m["probes"]:
        assert e["base"]["file"].endswith("Y9.rvt")
        assert e["the_ONE_thing_it_tests"] and e["if_PASS"] and e["if_FAIL"]

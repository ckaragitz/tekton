"""Stream-local tests for tools/subtractive.py (the subtractive ladder).

Pins the measured classification (partition sizes, group assignment law,
roster equivalence), the deletion law (cascade closures, the one detach
normalization, scrub + residual invariants read from the emitted reports),
the O1 permutation, and the staged-round bookkeeping.  No probe is rebuilt
here; artifact-dependent tests read accounting.json / probes.json /
classification.json and SKIP if the build has not run.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import subtractive as S                                        # noqa: E402

OUT = os.path.join(ROOT, "experiments", "subtractive")


# ---------------------------------------------------------------------------
# classification (computed once per session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cls_out():
    S._fb()._install_schema()                                  # noqa: SLF001
    return S.classify()


@pytest.fixture(scope="module")
def dels(cls_out):
    return S.deletion_sets(cls_out)


@pytest.fixture(scope="module")
def acct():
    p = os.path.join(OUT, "accounting.json")
    if not os.path.isfile(p):
        pytest.skip("accounting.json missing (build not run)")
    with open(p) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def probes():
    p = os.path.join(OUT, "probes.json")
    if not os.path.isfile(p):
        pytest.skip("probes.json missing (build not run)")
    with open(p) as fh:
        return json.load(fh)


def test_partition_sizes_pinned(cls_out):
    assert cls_out["sizes"] == S.EXPECT_SIZES
    assert len(cls_out["frame"]) == 6
    total = sum(cls_out["sizes"].values()) + 6
    assert total == 417


def test_partition_is_exact(cls_out):
    seen = set()
    for k in S.GROUPS:
        ids = set(cls_out["group_ids"][k])
        assert not (ids & seen), f"{k} overlaps another group"
        seen |= ids
    assert not (seen & cls_out["frame"])
    assert len(seen) == 411


def test_frame_roles_are_the_measured_six(cls_out):
    frame = cls_out["frame"]
    assert frame == {1410872, 1411008, 1410913, 1410912, 1410914, 1410915}


def test_nested_cluster_shape(cls_out):
    assert cls_out["nested_family"] == 1411054
    assert len(cls_out["nested_members"]) == 112
    s6 = set(cls_out["group_ids"]["S6"])
    assert {1411054, 1411142, 1411143, 1411144} <= s6
    assert len(s6) == 116


def test_class_map_covers_all_classes(cls_out):
    assert len(cls_out["class_to_group"]) == 72
    # every count adds back to 417
    n = sum(sum(m.values()) for m in cls_out["class_to_group"].values())
    assert n == 417


def test_class_map_key_assignments(cls_out):
    m = cls_out["class_to_group"]
    assert m["CategoryElem"] == {"S3": 2, "S4": 5, "S5": 43, "S6": 18}
    assert m["GStyleElem"]["S5"] == 43
    assert m["FontElem"] == {"S3": 1, "S4": 5, "S5": 15, "S6": 10}
    assert m["DBViewType"] == {"S4": 11, "S6": 10}
    assert m["Family"] == {"FRAME": 1, "S6": 1}
    assert m["UnitsElem"] == {"FRAME": 1}
    assert m["LoadCaseElem"] == {"S7": 8}
    assert m["ParamElemFamily"] == {"S6": 1, "S7": 1}
    assert m["SketchPlane"] == {"S1": 4, "S3": 2, "S4": 6, "S6": 3}
    assert m["LinearDimString"] == {"S2": 4, "S6": 7}
    assert m["Alignment"] == {"S2": 7}
    assert m["RadialDim"] == {"S6": 3}


def test_equivalence_pins(cls_out):
    eq = cls_out["equivalence"]
    assert eq["level"] == 1410875
    assert eq["plan_view"] == 1410877
    assert eq["extrusion"] == 1410972
    assert eq["level_attributes"] == 1410873
    assert eq["sketch"] == 1410971
    assert eq["curves"] == [1410973, 1410974, 1410975, 1410976]
    assert eq["sketch_plane"] == 1410981
    assert eq["plan_viewer"] == 1410876
    assert eq["plan_drawing"] == 1410878
    assert eq["plan_viewport"] == 1410879
    assert eq["plan_view_type"] == 1411162
    assert eq["plan_extent"] == 1411001
    assert eq["plan_sketch_plane"] == 1411228
    assert eq["sun"] == 1411204
    assert len(eq["sketch_alignment_ref_planes"]) == 4
    assert len(eq["sf_params"]) == 1
    assert "NO donor equivalent" in eq["connector_layer"]


def test_s5_halves_partition_s5(cls_out):
    s5 = set(cls_out["group_ids"]["S5"])
    a, b = set(cls_out["s5a"]), set(cls_out["s5b"])
    assert a | b == s5 and not (a & b)
    assert len(a) == 109 and len(b) == 16


# ---------------------------------------------------------------------------
# the deletion law (closures)
# ---------------------------------------------------------------------------

def test_closure_sizes_pinned(dels):
    for k in S.GROUPS:
        d = dels[f"SUB_{k}"]
        assert d["n_seed"] == S.EXPECT_SIZES[k]
        assert d["n_closure"] == S.EXPECT_SIZES[k] + S.EXPECT_PULLS[k]
    assert dels["SUB_ALL"]["n_closure"] == 411


def test_clean_singles_have_no_pulls(dels):
    assert dels["SUB_S2"]["pulled"] == []
    assert dels["SUB_S6"]["pulled"] == []
    assert dels["SUB_S5B"]["pulled"] == []


def test_detach_fires_only_for_s6(dels):
    for name, d in dels.items():
        if name == "SUB_S6":
            assert d["detached"] == [1410873]
        else:
            assert d["detached"] == []


def test_closures_never_touch_frame(cls_out, dels):
    frame = cls_out["frame"]
    for d in dels.values():
        assert not (set(d["closure"]) & frame)


def test_sub_all_is_union_of_groups(cls_out, dels):
    union = set()
    for k in S.GROUPS:
        union |= set(cls_out["group_ids"][k])
    assert set(dels["SUB_ALL"]["closure"]) == union


def test_s3_cascade_sweeps_view_furniture(dels):
    cen = dels["SUB_S3"]["pull_census"]
    assert cen.get("S4:Viewer") == 6
    assert cen.get("S4:DBViewSection") == 4
    assert cen.get("S2:Alignment") == 7


def test_s5_cascade_pulls_dims(dels):
    cen = dels["SUB_S5"]["pull_census"]
    assert cen.get("S2:Alignment") == 7
    assert cen.get("S2:LinearDimString") == 4
    assert cen.get("S6:LinearDimString") == 1


# ---------------------------------------------------------------------------
# built artifacts (accounting.json)
# ---------------------------------------------------------------------------

def test_all_probes_built_and_gated(acct):
    for name in S.LADDER:
        assert name in acct["built"], f"{name} not built"
        g = acct["gates"][name]
        assert g["gates_ok"] is True, f"{name}: {g}"


def test_gate_law_per_probe(acct):
    for name in S.LADDER:
        g = acct["gates"][name]
        assert g["validator_errors"] == 0
        assert g["validator_unexpected"] == 0
        assert g["four_registry_coherent"] is True
        assert g["load_hop_units_added"] == 1
        assert g["instance_hop_units_added"] == 0
        assert g["identity"] == "PASS"
        assert g["blob_all_units_64B"] is True
        assert g["blob_added_nonce_verified"] is True
        assert g["blob_units_added"] == 1
        assert g["famdoc_refs_unresolved_anywhere"] == 0


def test_deletion_arithmetic(acct, dels):
    for name in S.LADDER:
        if name == "SUB_O1":
            continue
        info = acct["built"][name]
        d = info["deletion"]
        assert d["n_elements_before"] == 452
        assert d["n_deleted"] == dels[name]["n_closure"]
        assert d["n_elements_after"] == 452 - d["n_deleted"]
        assert d["survivor_residual_refs"] == 0
        assert info["n_elements"] == d["n_elements_after"]


def test_adoc_row_arithmetic(acct, dels):
    for name in S.LADDER:
        if name == "SUB_O1":
            continue
        sw = acct["built"][name]["adoc_swap"]
        assert sw["elem_rows_before"] == 417
        assert sw["elem_rows_dropped"] == dels[name]["n_closure"]
        assert len(sw["elem_rows_appended"]) == 35
        assert sw["elem_rows_total"] == 417 - sw["elem_rows_dropped"] + 35


def test_sub_all_reaches_lean_shape(acct):
    info = acct["built"]["SUB_ALL"]
    assert info["n_elements"] == 41
    assert info["deletion"]["n_deleted"] == 411


def test_zeroed_classes_read(acct):
    assert acct["built"]["SUB_S2"]["classes_zeroed_documentwide"] == ["Alignment"]
    z_all = acct["built"]["SUB_ALL"]["classes_zeroed_documentwide"]
    assert "CategoryElem" in z_all and "FontElem" in z_all
    # SUB_S5 zeroes only the classes with NO surviving instance anywhere --
    # the nested cluster's own DimensionStyle/LeaderStyle copies survive S5
    z5 = acct["built"]["SUB_S5"]["classes_zeroed_documentwide"]
    assert z5 == ["Alignment", "ReferenceViewerAttributes",
                  "RevisionCloudAttr", "SpotElevationStyle"]
    z6 = acct["built"]["SUB_S6"]["classes_zeroed_documentwide"]
    assert "FamilySymbol" in z6 and "FamilySurrogate" in z6
    # ours remain: classes we carry never zero
    for name in S.LADDER:
        if name == "SUB_O1":
            continue
        z = acct["built"][name]["classes_zeroed_documentwide"]
        for keep in ("ExtrusionElem", "Level", "RefPlane", "DBViewPlan",
                     "ParamElemFamily", "ConnectorElem"):
            assert keep not in z, f"{name} zeroed carried class {keep}"


def test_detach_applied_in_s6_build(acct):
    rep_dir = os.path.join(OUT, "_build", "SUB_S6", "deletion_report.json")
    with open(rep_dir) as fh:
        rep = json.load(fh)
    da = rep.get("detach_applied")
    assert da and da["now"] == -1 and isinstance(da["m_familyTagId_was"], int)
    assert rep["detached"] and len(rep["detached"]) == 1


def test_scrub_census_present(acct):
    d = acct["built"]["SUB_ALL"]["deletion"]["scrub_census"]
    assert d["Family.m_familyIds"] == 299
    assert d["hdr.m_parents.m_deletion"] == 299
    assert "Family.m_deletableElements" in d


def test_adoc_registry_dangling_censused(acct):
    sw = acct["built"]["SUB_ALL"]["adoc_swap"]
    assert sw["registry_dangling_total"] > 0
    assert isinstance(sw["registry_dangling_census"], dict)
    assert acct["built"]["SUB_S2"]["adoc_swap"]["registry_dangling_total"] == 0


def test_bases_and_recipe_pins(acct):
    for name in S.LADDER:
        info = acct["built"][name]
        if name == "SUB_O1":
            assert info["base"].endswith("G_ABPD.rvt")
            assert "B0" in info["recipe"]
            assert "corpus_symbol_form" in info["recipe"]
        else:
            assert info["base"].endswith("rstbasicsampleproject.rvt")
            assert info["placement"].startswith("uniform template path")


# ---------------------------------------------------------------------------
# SUB_O1 (the order probe)
# ---------------------------------------------------------------------------

def test_o1_permutation_is_bijection(acct):
    with open(os.path.join(OUT, "_build", "SUB_O1_permutation.json")) as fh:
        rep = json.load(fh)
    perm = {int(k): int(v) for k, v in rep["permutation"].items()}
    assert sorted(perm) == sorted(perm.values())
    assert rep["n_elements"] == 41
    assert rep["n_moved"] >= 30            # the orders differ radically


def test_o1_order_follows_donor_convention(acct):
    info = acct["built"]["SUB_O1"]
    after = info["permutation"]["class_order_after"]
    assert after[:9] == ["Family", "LevelAttributes", "Level", "Viewer",
                         "DBViewPlan", "DBDrawing", "Viewport", "RefPlane",
                         "RefPlane"]
    assert after[-2:] == ["ElectricalLoadClassification", "ConnectorElem"]
    # UnitsElem is LATE in the donor convention (ours authored it 2nd)
    assert after.index("UnitsElem") > after.index("ExtrusionElem")
    before = info["permutation"]["class_order_before"]
    assert before[1] == "UnitsElem"
    assert sorted(before) == sorted(after)


def test_o1_symbol_form_gate(acct):
    info = acct["built"]["SUB_O1"]
    forms = info.get("symbol_form") or {}
    assert forms and all(f["ok"] for f in forms.values())


def test_o1_role_rank_is_strictly_ordered():
    ranks = list(S.O1_ROLE_RANK.values())
    assert len(set(ranks)) == len(ranks)
    assert S.O1_ROLE_RANK["self_family"] < S.O1_ROLE_RANK["ref_level"]
    assert S.O1_ROLE_RANK["units"] > S.O1_ROLE_RANK["extrusion"]
    assert S.O1_ROLE_RANK["family_param"] > S.O1_ROLE_RANK["units"]
    assert S.O1_ROLE_RANK["connector"] == max(ranks)


# ---------------------------------------------------------------------------
# probes.json (the decision table)
# ---------------------------------------------------------------------------

def test_probes_json_order_and_bases(probes):
    rungs = [p["rung"] for p in probes["probes"]]
    assert rungs == list(S.LADDER)
    assert probes["upload_order_max_information_first"] == list(S.LADDER)
    for p in probes["probes"]:
        if p["rung"] == "SUB_O1":
            assert p["base"].endswith("G_ABPD.rvt")
        else:
            assert p["base"].endswith("rstbasicsampleproject.rvt")
        assert p["md5"], f"{p['rung']} missing md5"
        assert p["gates"]["gates_ok"] is True


def test_probes_json_md5s_match_accounting(probes, acct):
    for p in probes["probes"]:
        assert p["md5"] == acct["built"][p["rung"]]["md5"]


def test_reading_matrix_branch_coverage(probes):
    r = probes["reading_the_matrix"]
    for key in ("CTRL FAIL (either)", "the bracket", "SUB_Sx FAIL (single)",
                "SUB_Sx PASS (single)", "ALL singles PASS + SUB_ALL FAIL",
                "ALL singles FAIL", "SUB_ALL PASS",
                "SUB_S5A/S5B (read on SUB_S5 FAIL)", "SUB_O1 PASS",
                "SUB_O1 FAIL", "honest residue"):
        assert key in r, f"reading matrix missing branch {key!r}"
    assert probes["controls"]["rst"]["source"].endswith(
        "rstbasicsampleproject.rvt")
    assert probes["controls"]["g_abpd"]["source"].endswith("G_ABPD.rvt")


def test_probe_files_exist_with_md5(probes):
    import hashlib
    for p in probes["probes"]:
        path = os.path.join(ROOT, p["file"])
        assert os.path.isfile(path), f"{p['file']} missing"
        h = hashlib.md5()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        assert h.hexdigest() == p["md5"], f"{p['rung']} md5 drifted"


# ---------------------------------------------------------------------------
# classification.json + author_spec.json artifacts
# ---------------------------------------------------------------------------

def test_classification_json_written():
    p = os.path.join(OUT, "classification.json")
    if not os.path.isfile(p):
        pytest.skip("classification.json missing (classify not run)")
    with open(p) as fh:
        d = json.load(fh)
    assert d["sizes"] == S.EXPECT_SIZES
    assert set(d["groups"]) == set(S.GROUPS)
    assert "roster_equivalence" in d and "class_to_group" in d
    assert d["detach_law"] == S.DETACH_LAW
    for k in S.GROUPS:
        assert d["groups"][k]["n"] == S.EXPECT_SIZES[k]


def test_author_spec_written():
    p = os.path.join(OUT, "author_spec.json")
    if not os.path.isfile(p):
        pytest.skip("author_spec.json missing (spec not run)")
    with open(p) as fh:
        d = json.load(fh)
    s5 = d["S5_styles_categories_fonts"]
    s6 = d["S6_nested_annotation_family"]
    assert s5["panelboard_counts"]["CategoryElem"] == 84
    assert s5["panelboard_counts"]["FontElem"] == 41
    assert s5["unknowns"] and s6["unknowns"]
    assert s6["column_donor_cluster"]["n_registered_members"] == 112
    assert s6["panelboard_counts"]["Family_total_incl_self"] == 4
    assert d["rme_panelboard_reference"]["n_elements"] == 549


# ---------------------------------------------------------------------------
# the deletion primitives
# ---------------------------------------------------------------------------

def test_prune_int_list():
    lst = [1, 2, 3, 4, True]
    n = S._prune_int_list(lst, {2, 4})                         # noqa: SLF001
    assert n == 2 and lst == [1, 3, True]


def test_prune_entry_lists_drops_referencing_rows():
    node = {"rows": [{"id": 5, "x": 1}, {"id": 6, "x": 2}, 7, "s"]}
    census = {}
    S._prune_entry_lists(node, {6, 7}, census, "t")            # noqa: SLF001
    assert node["rows"] == [{"id": 5, "x": 1}, "s"]
    assert census == {"t.rows[]": 2}


def test_registry_law_constants():
    assert "m_familyIds" in S.FAMILY_REG_KEYS
    assert "m_oFamDimConstrMgr" in S.FAMILY_REG_KEYS
    assert "m_refs" in S.FAMILY_REG_KEYS
    assert S.SKETCH_REG_KEYS == ("m_dimIds", "m_dimData")
    assert S.PARENT_LISTS == ("m_deletion", "m_regenOnly",
                              "m_appearanceParents")


def test_ladder_names_are_collision_safe():
    # experiments/acceptance already holds genesis_deletion's D_all.rvt --
    # on a case-insensitive filesystem D_ALL would collide; the SUB_ prefix
    # is the guard
    for name in S.LADDER:
        assert name.startswith("SUB_")

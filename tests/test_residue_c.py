"""tests for rvt.genesis.residue_c (GENESIS-12: the residue endgame on G_ABPD
+ the walls+families fix forms) and the committed residue_c / g12 artifacts."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import residue_c as RC                              # noqa: E402

RESIDUE_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_c")
G12_DIR = os.path.join(ROOT, "experiments", "render", "g12")

needs_gabpd = pytest.mark.skipif(not os.path.exists(RC.G_ABPD),
                                 reason="G_ABPD not present")
needs_artifacts = pytest.mark.skipif(
    not os.path.exists(os.path.join(RESIDUE_DIR, "probes.json")),
    reason="residue_c batch not built")
needs_g12 = pytest.mark.skipif(
    not os.path.exists(os.path.join(G12_DIR, "probes.json")),
    reason="g12 batch not built")


# ---------------------------------------------------------------------------
# the walls+families fix forms (pure)
# ---------------------------------------------------------------------------

def test_famdim_constr_empty_is_the_corpus_shape():
    f = RC.famdim_constr_empty()
    assert f["ptr_class"] == "FamDimConstrMgrImpl"
    v = f["value"]
    assert v["m_pFam"] == {"weakref": 2}
    # every other field is an empty list (the corpus-identical empty form)
    others = {k: x for k, x in v.items() if k != "m_pFam"}
    assert len(others) == 10
    assert all(x == [] for x in others.values())


def test_move_restrictions_empty_is_the_corpus_shape():
    m = RC.move_restrictions_empty()
    assert m["ptr_class"] == "Matrix"
    assert m["value"] == {"m_nRows": 0, "m_ncols": 3, "m_bUseSingleArray": True,
                          "m_arr": [], "m_rows": []}


def test_fix_family_layer_records_is_idempotent_and_targeted():
    class _Rec:
        class_id = 999

    class _Doc:
        def __init__(self, values):
            self._v = values

        def value(self, eid):
            return self._v[eid]

        def record(self, eid):
            return _Rec()

    doc = _Doc({
        1: {"m_id": 1, "m_oFamDimConstrMgr": None},                  # broken family
        2: {"m_id": 2, "m_oFamDimConstrMgr": {"ptr_class": "FamDimConstrMgrImpl"}},
        3: {"m_id": 3, "m_pMoveRestrictions": None},                 # broken symbol
        4: {"m_id": 4, "m_pMoveRestrictions": {"ptr_class": "Matrix"}},
    })
    out = RC.fix_family_layer_records(doc, family_ids=[1, 2], symbol_ids=[3, 4])
    assert sorted(out) == [1, 3]                       # lawful ones skipped
    assert out[1][102][1]["m_oFamDimConstrMgr"]["ptr_class"] == "FamDimConstrMgrImpl"
    assert out[3][102][1]["m_pMoveRestrictions"]["ptr_class"] == "Matrix"
    # the input doc's values were not mutated
    assert doc.value(1)["m_oFamDimConstrMgr"] is None


# ---------------------------------------------------------------------------
# constructors (pure)
# ---------------------------------------------------------------------------

def test_our_year_schedule_changes_only_the_name():
    slot = {"m_scheduleName": "Off - 24 Hours", "m_daySchedules": [7] * 365,
            "m_id": 42}
    v = RC.our_year_schedule(slot, "GEN Off - 24 Hours")
    assert v["m_scheduleName"] == "GEN Off - 24 Hours"
    assert v["m_daySchedules"] == slot["m_daySchedules"]
    assert slot["m_scheduleName"] == "Off - 24 Hours"          # input untouched


def test_our_type_preview_nulls_only_the_image():
    slot = {"m_componentType": 600634, "m_bIsForTypePreview": True,
            "m_oPreviewImage": {"ptr_class": "ARasterImage", "value": {"m_width": 128}}}
    v = RC.our_type_preview(slot)
    assert v["m_oPreviewImage"] is None
    assert v["m_componentType"] == 600634
    assert slot["m_oPreviewImage"] is not None


def test_clean_view_header_drops_exactly_the_link_symbol():
    hdr = {"m_parents": {"ptr_class": "ElementParents", "value": {
        "m_deletion": [201, 230, RC.LINK_SYMBOL, 375],
        "m_appearanceParents": [11],
    }}}
    h = RC.clean_view_header(hdr)
    assert RC.LINK_SYMBOL not in h["m_parents"]["value"]["m_deletion"]
    assert h["m_parents"]["value"]["m_deletion"] == [201, 230, 375]
    assert h["m_parents"]["value"]["m_appearanceParents"] == [11]
    assert RC.LINK_SYMBOL in hdr["m_parents"]["value"]["m_deletion"]


def test_rewired_area_measure_unwires_topology():
    obj = {"m_id": RC.AREA_MEASURE, "m_areaSchemePlanTopologyElemId": RC.TOPOLOGY}
    hdr = {"m_parents": {"value": {"m_deletion": [RC.AREA_MEASURE, 9492, RC.TOPOLOGY]}}}
    v, h = RC.rewired_area_measure(obj, hdr)
    assert v["m_areaSchemePlanTopologyElemId"] == -1
    assert RC.TOPOLOGY not in h["m_parents"]["value"]["m_deletion"]


# ---------------------------------------------------------------------------
# plans against the live parent
# ---------------------------------------------------------------------------

@needs_gabpd
def test_plans_cover_the_claimed_slots():
    from rvt.mutate import Document
    doc = Document.from_file(RC.G_ABPD)
    y = RC.plan_year(doc)
    assert len(y.records) == 27 and y.seqs == (102,)
    p = RC.plan_preview(doc)
    assert sorted(p.records) == sorted(RC.PREVIEW_SLOTS) and p.seqs == (102,)
    h = RC.plan_hdr(doc)
    assert sorted(h.records) == sorted(RC.VIEW_HEADER_SLOTS) and h.seqs == (101,)
    a = RC.plan_area(doc)
    assert list(a.records) == [RC.AREA_MEASURE] and a.seqs == (101, 102)
    deep = RC.plan_deep(doc)
    assert set(deep.records) == (set(y.records) | set(p.records)
                                 | set(h.records) | set(a.records))
    # every year name comes from OUR day-schedule library (the GEN prefix)
    for slot, by in y.records.items():
        _cid, value = by[102]
        assert value["m_scheduleName"].startswith("GEN ")


@needs_gabpd
def test_year_schedule_names_still_autodesks_in_parent():
    """The census fact: residue_a2 reproduced the year schedules byte-identical,
    so the PARENT still carries Autodesk's names (localized in dach => free
    value).  This is what RC_year retires."""
    from rvt.mutate import Document
    doc = Document.from_file(RC.G_ABPD)
    names = {doc.value(e).get("m_scheduleName")
             for e in doc.ids_of_class("BuildingOperatingYearSchedule")}
    assert "Off - 24 Hours" in names
    assert not any(str(n).startswith("GEN ") for n in names)


# ---------------------------------------------------------------------------
# the committed batch artifacts
# ---------------------------------------------------------------------------

@needs_artifacts
def test_rung_reports_valid_and_byte_delta_asserted():
    rungs = ("RC_year", "RC_preview", "RC_hdr", "RC_area", "RC_deep")
    if not any(os.path.exists(os.path.join(RESIDUE_DIR, f"{n}.rvt"))
               for n in rungs):
        pytest.skip("rung binaries are git-ignored and absent (fresh clone)")
    for name in ("RC_year", "RC_preview", "RC_hdr", "RC_area", "RC_deep"):
        p = os.path.join(RESIDUE_DIR, f"{name}.json")
        with open(p) as fh:
            r = json.load(fh)
        assert r["verdict"] == "VALID", name
        assert r["validator"]["errors"] == 0, name
        assert r["byte_delta"]["assertion_holds"], name
        assert r["byte_delta"]["global_latest_identical"], name
        assert r["byte_delta"]["global_elemtable_identical"], name
        assert r["new_object_reference_check"]["dangling"] == 0, name
        assert os.path.exists(os.path.join(RESIDUE_DIR, f"{name}.rvt")), name


@needs_artifacts
def test_rc_zero_retired_the_stragglers_lawfully():
    with open(os.path.join(RESIDUE_DIR, "RC_zero.json")) as fh:
        z = json.load(fh)
    assert z["ok"] is True
    assert z["composer_verdict"] == "COMPOSED-VALID"
    assert z["stragglers_still_present"] == []
    gone = set(z["stragglers_expected_gone"])
    assert {RC.LINK_SYMBOL, RC.DATASTORAGE, RC.TOPOLOGY} <= gone
    assert set(RC.ROOM_CONSTELLATION) <= gone
    with open(os.path.join(RESIDUE_DIR, "RC_zero.manifest.json")) as fh:
        m = json.load(fh)
    assert m["verdict"] == "COMPOSED-VALID"
    law = m["phase_2_deletions"]["reduce_law"]
    assert law["verdict"] == "EDIT-FREE" and law["ok"] is True
    assert law["removed"] == 11 and law["added"] == 0 and law["survivors_edited"] == 0


@needs_artifacts
def test_probes_json_declares_the_certified_base():
    with open(os.path.join(RESIDUE_DIR, "probes.json")) as fh:
        man = json.load(fh)
    assert man["base"]["file"].endswith("G_ABPD.rvt")
    assert man["base"]["certification"], "the base must carry its ledger entry"
    assert man["standing_control"]["md5"]
    order = man["upload_order_bisection_first"]
    assert order[0] == "RC_zero" and "RC_deep" in order
    for probe in man["probes"]:
        assert probe["base"]["file"].endswith("G_ABPD.rvt")
        assert probe["derived_from"].endswith("G_ABPD.rvt")
        assert probe["the_ONE_thing_it_tests"]
        assert probe["if_PASS"] and probe["if_FAIL"]


@needs_artifacts
def test_census_dispositions_are_complete_and_honest():
    with open(os.path.join(RESIDUE_DIR, "census.json")) as fh:
        c = json.load(fh)
    disp = c["by_disposition"]
    assert sum(disp.values()) == c["autodesk_serialization_identical"]
    assert disp.get("RC-YEAR") == 27
    assert disp.get("RC-PREVIEW") == 2
    assert set(disp) <= set(RC.DISPOSITION)
    # the already-retired stragglers are verified ABSENT
    for e, status in c["already_retired_stragglers"].items():
        assert status.startswith("ABSENT"), (e, status)


# ---------------------------------------------------------------------------
# the g12 probes (walls+families mechanism + the wall solid)
# ---------------------------------------------------------------------------

@needs_g12
def test_wf_pair_isolates_exactly_the_two_records():
    with open(os.path.join(G12_DIR, "WF_report.json")) as fh:
        r = json.load(fh)
    assert r["defect_present_in_nofix"] == {
        "family_m_oFamDimConstrMgr_null": True,
        "symbol_m_pMoveRestrictions_null": True}
    assert r["defect_absent_in_fix"] == {
        "family_m_oFamDimConstrMgr_present": True,
        "symbol_m_pMoveRestrictions_present": True}
    assert r["pair_delta"]["assertion_exactly_the_two_records"] is True
    assert r["pair_delta"]["latest_identical"] is True
    assert r["pair_delta"]["embedded_units_identical"] is True
    assert r["validator_WF_nofix"]["errors"] == 0
    assert r["validator_WF_fix"]["errors"] == 0
    # objlint: the two CRITICAL violations exist in nofix, none in fix
    crit = r["objlint_critical_findings"]
    fields = {f["field"] for f in crit["WF_nofix"]}
    assert fields == {"m_oFamDimConstrMgr.#ptr", "m_pMoveRestrictions.#ptr"}
    assert crit["WF_fix"] == []
    assert r["objlint_mechanism_confirmed"] is True


@needs_g12
def test_w1_wall_probe_is_baked_and_valid():
    with open(os.path.join(G12_DIR, "W1_report.json")) as fh:
        w = json.load(fh)
    assert w["validator"]["errors"] == 0
    rb = w["readback"]
    assert rb["has_baked_geometry"] is True
    assert rb["kind"] == "brep"
    assert rb["n_faces"] == 6 and rb["n_edges"] == 12
    assert w["bake"]["verdict"] == "VALID"
    assert "mutate.py untouched" in w["bake"]["mechanism"]


@needs_g12
def test_g12_probes_json_bases_are_certified_files():
    with open(os.path.join(G12_DIR, "probes.json")) as fh:
        man = json.load(fh)
    rungs = {p["rung"]: p for p in man["probes"]}
    assert set(rungs) == {"WF_nofix", "WF_fix", "W1_gabpd_wall_solid"}
    assert rungs["WF_nofix"]["base"]["file"].endswith("walls_only.rvt")
    assert rungs["WF_fix"]["base"]["file"] == rungs["WF_nofix"]["base"]["file"]
    assert rungs["W1_gabpd_wall_solid"]["base"]["file"].endswith("G_ABPD.rvt")
    for p in man["probes"]:
        assert p["base"]["certification"], p["rung"]


# ---------------------------------------------------------------------------
# one end-to-end emission (temp dir)
# ---------------------------------------------------------------------------

@needs_gabpd
def test_emit_rc_area_end_to_end(tmp_path):
    from rvt.mutate import Document
    doc = Document.from_file(RC.G_ABPD)
    rep = RC.emit_rung(RC.plan_area(doc), RC.G_ABPD, str(tmp_path), doc=doc)
    assert rep["verdict"] == "VALID"
    assert rep["validator"]["errors"] == 0
    assert rep["byte_delta"]["assertion_holds"]
    out = Document.from_file(os.path.join(str(tmp_path), "RC_area.rvt"))
    assert out.value(RC.AREA_MEASURE)["m_areaSchemePlanTopologyElemId"] == -1
    hdr = out.value(RC.AREA_MEASURE, seq=101)
    assert RC.TOPOLOGY not in hdr["m_parents"]["value"]["m_deletion"]

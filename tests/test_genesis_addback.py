"""tests for tools/genesis_addback.py -- the add-back probes + the
registry-parity audit (genesis-addback stream).

These pin the machinery the probes rest on (byte-preserving transplant,
document-object reinstatement, the schema-typed re-point, the class-keyed
parity signatures) and the emitted deliverables' certification, using
the K-ladder files as fixtures.  Full probe builds are ~25-75 s each; the
built deliverables under experiments/genesis/addback/ are certified as
they stand on disk (built by the driver), and the mechanics are exercised
on small in-memory / temp-dir cases.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import genesis_addback as GB                                       # noqa: E402

TRIAGE = os.path.join(ROOT, "experiments", "genesis", "triage")
ADDBACK = os.path.join(ROOT, "experiments", "genesis", "addback")
K1 = os.path.join(TRIAGE, "K1.rvt")
K5 = os.path.join(TRIAGE, "K5.rvt")
K6 = os.path.join(TRIAGE, "K6.rvt")

needs_fixtures = pytest.mark.skipif(
    not (os.path.exists(K1) and os.path.exists(K5) and os.path.exists(K6)),
    reason="K-ladder fixtures (experiments/genesis/triage/K1,K5,K6.rvt) not built")


# ---------------------------------------------------------------------------
# shared fixtures (module scope: the Facts loads are the expensive part)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def k1():
    return GB.Facts(K1)


@pytest.fixture(scope="module")
def k5():
    return GB.Facts(K5)


@pytest.fixture(scope="module")
def k6():
    return GB.Facts(K6)


# ---------------------------------------------------------------------------
# 1. the removal analyses: exactly what K5 / K6 took away
# ---------------------------------------------------------------------------

@needs_fixtures
def test_k5_removal_split_covered_vs_uncovered(k1, k5):
    ana = GB.k5_removal_analysis(k5, k1)
    assert len(ana["removed_ids"]) == 96
    # covered = removed AND buildable by the S3/S5 constellation
    cons = GB.constellation_classes()
    for c in ana["covered_classes"]:
        assert c in cons
    for c in ana["uncovered_classes"]:
        assert c not in cons
    # the classes our constructors do NOT cover are the ones restored verbatim
    unc = set(ana["uncovered_classes"])
    assert {"AreaReportSettingsElem", "AssemblyCodeTable", "NumberingSchema",
            "AllPlanTopologies", "ViewSheetSet"} <= unc
    assert set(ana["covered_ids"]).isdisjoint(ana["uncovered_ids"])
    assert set(ana["covered_ids"]) | set(ana["uncovered_ids"]) == set(ana["removed_ids"])


@needs_fixtures
def test_k6_removal_builtin_catalog_is_exactly_our_enum(k1, k6):
    ana = GB.k6_removal_analysis(k6, k1)
    assert ana["removed_total"] == 2151
    # the built-in object-style rows K6 deleted vs everything else
    assert len(ana["builtin_style_deleted_ids"]) == 1348
    assert len(ana["restore_ids"]) == 2151 - 1348
    assert ana["pen_table_deleted_by_K6"] is True           # the K-ladder confound R2 removes
    # our frozen enum covers EXACTLY the deleted (category, style type) pairs
    ids = GB.id_source_for(K1, K6)
    recs, rep, remap = GB.build_our_k6_catalog(k6, k1, ids)
    assert rep["missing_pairs"] == 1348
    assert rep["our_rows_generated"] == 1348
    assert rep["missing_pairs_our_enum_lacks_count"] == 0    # 0 pairs our enum lacks
    assert len(remap) == 1348 and len(set(remap.values())) == 1348   # 1:1 re-point map
    assert rep["by_style_type"] == {"projection": 1018, "cut": 330}


# ---------------------------------------------------------------------------
# 2. our K5 delta: only the DELETED classes, wired to K5's own companions
# ---------------------------------------------------------------------------

@needs_fixtures
def test_our_k5_delta_never_duplicates_a_kept_singleton(k1, k5):
    ids = GB.id_source_for(K1, K5)
    recs, delta = GB.build_our_k5_delta(k5, k1, ids)
    ours = {r.class_name for r in recs}
    still_present = set(k5.census())
    # constellation classes K5 KEPT must not be re-added by us
    for cls in ("RbsPipeSettingsElem", "RbsDuctSettingsElem", "WorksetVisibilitySettingsElem",
                "MEPComponentTracker", "MEPNetworkTracker", "MEPNetworkDataElem",
                "KeynoteTable", "RevisionNumberingSequence", "ProjectRevision",
                "AllProjectRevisions", "AreaMeasureElem", "EnergyDataSettings", "DBViewType"):
        assert cls in still_present
        assert cls not in ours, f"our delta must not duplicate K5's kept {cls}"
    # and the covered classes are all produced
    for cls in ("PenWidthTableElem", "StructSettingsElem", "RbsWireSizesElem",
                "RbsDbViewSystemNavigator", "MEPSystemTracker", "KeynotingSystem"):
        assert cls in ours
    # every record is schema-valid and byte-exact reversible
    for r in recs:
        assert r.roundtrip()["ok"], f"{r.class_name}#{r.elem_id} not byte-exact"


@needs_fixtures
def test_our_k5_delta_wiring_uses_k5_ids(k1, k5):
    w = GB.k5_wiring(k5, k1)
    for key in ("units", "phase_new", "phase_filter", "document_sun", "level1",
                "workset_visibility", "mep_component_tracker", "pipe_settings",
                "duct_settings", "keynote_table"):
        assert w[key] > 0 and w[key] in k5.ids, f"{key} must be a K5 element"
    # the document sun is the one the sample's own presets / project view share
    assert w["document_sun"] == 54520
    # the wire catalog symbols are the sample's own (present in K5)
    assert set(w["wire_materials_by_name"].values()) <= k5.ids
    assert len(w["wire_insulations_by_name"]) == 26
    # KeynoteTable survived K5: our KeynotingSystem names IT
    ids = GB.id_source_for(K1, K5)
    recs, _delta = GB.build_our_k5_delta(k5, k1, ids)
    ks = [r for r in recs if r.class_name == "KeynotingSystem"][0]
    assert ks.obj["m_keynoteTableId"] == w["keynote_table"]
    # the navigator's deferred parent is OUR new MEPSystemTracker
    nav = [r for r in recs if r.class_name == "RbsDbViewSystemNavigator"][0]
    sys_trk = [r for r in recs if r.class_name == "MEPSystemTracker"][0]
    assert sys_trk.elem_id in nav.header["m_parents"]["value"]["m_deferredParents"]
    # only the 2 house browser organizations (the 4 'all' defaults survive in K5)
    orgs = [r for r in recs if r.class_name == "BrowserOrganization"]
    assert len(orgs) == 2 and not any(o.refs.get("default") for o in orgs)


# ---------------------------------------------------------------------------
# 3. the transplant: verbatim record bytes at original ids
# ---------------------------------------------------------------------------

@needs_fixtures
def test_extract_element_records_is_byte_preserving(k1, k5):
    ana = GB.k5_removal_analysis(k5, k1)
    ids = ana["uncovered_ids"][:6]
    recs, plans = GB.extract_element_records(K1, ids)
    for i in ids:
        assert set(recs[i]) == {101, 102, 103}
        assert plans[i].elem_id == i and plans[i].original_id == i
        # the bytes decode to the same class as in the donor
        from rvt.objects import iter_records
        for seq in (102,):
            rr = list(iter_records(recs[i][seq], seq))
            assert len(rr) == 1 and rr[0].elem_id == i
            assert k1.doc.dec.class_name(rr[0].class_id) == k1.cls_of(i)


@needs_fixtures
def test_transplant_then_reinstate_reference_object(tmp_path, k1, k5):
    """restore two uncovered rows into K5 and reinstate K1's document
    object purged of the rest: validator-clean, 0 NEW dangling."""
    ana = GB.k5_removal_analysis(k5, k1)
    restore = [i for c in ("AssemblyCodeTable", "KeynotingSystem")
               for i in ana["by_class"].get(c, [])][:2]
    assert restore
    t1 = str(tmp_path / "t1.rvt")
    t2 = str(tmp_path / "t2.rvt")
    s1 = GB.transplant(K5, K1, restore, t1)
    assert s1["restored"] == len(restore)
    assert s1["verify_written"]["walker_errors"] == 0
    still_absent = set(ana["removed_ids"]) - set(restore)
    s2 = GB.reinstate_reference_latest(t1, k1.latest_payload, t2, still_absent=still_absent)
    assert s2["purged_ids"] > 0
    cert = GB.certify(t2, base_tree_refs_absent=GB.base_absent_refs(k1),
                      our_ids=[], restored_ids=restore)
    assert cert["validator"]["ok"] and cert["validator"]["errors"] == 0
    assert cert["dangling_NEW_count"] == 0
    assert cert["restored_ids_present"] == len(restore)


# ---------------------------------------------------------------------------
# 4. the schema-typed RE-POINT
# ---------------------------------------------------------------------------

@needs_fixtures
def test_remap_ids_in_tree_rewrites_every_reference(k1):
    tree = k1.tree_copy()
    # pick a built-in gstyle row id referenced by CategoryTracking
    ct = GB.GA._appinfo_body(tree, "CategoryTracking")
    row = next(r for r in ct["m_gstyleData"]
               if isinstance(r.get("m_categoryId"), int) and r["m_categoryId"] < 0)
    old = row["m_gstyleId"]
    hits = GB.remap_ids_in_tree(tree, {old: 999_999_999})
    assert sum(hits.values()) >= 1
    assert row["m_gstyleId"] == 999_999_999
    # no leaf still names the old id
    assert old not in GB.referenced_ids(tree)


# ---------------------------------------------------------------------------
# 5. the parity engine
# ---------------------------------------------------------------------------

@needs_fixtures
def test_parity_of_a_file_against_itself_is_clean(k1):
    """the audit turned on the reference itself: zero severity-0."""
    par = GB.parity_compare(K1, K1, label_ref="K1", label_subj="K1b")
    sev0 = [m for m in par["mismatches"] if m["severity"] == 0]
    assert sev0 == [], f"self-comparison must be clean, got {sev0[:3]}"


@needs_fixtures
def test_default_group_map_derives_view_family_constants(k1):
    dmap = GB.derive_default_group_map(k1)
    fg = dmap["family_group"]
    # the compiled-in view-family default groups
    assert fg[102] == 62      # 3D view family
    assert fg[109] == 71      # floor plan
    assert fg[111] == 72      # ceiling plan
    assert fg[120] == 70      # structural plan
    assert dmap["group_class"][110] == "ConstructionSetProject"
    assert dmap["group_class"][15] == "Level"


@needs_fixtures
def test_cell_kind_rule_holds_on_the_reference(k1):
    """every element holding an ExternalFileReferenceCell is in set 1200,
    every ESEntityCell holder in set -100 (the rule R3 / KNOWLEDGE rely on)."""
    holders = GB.cell_holders(k1)
    body = GB.GA._appinfo_body(k1.tree, "ElemsSetWithCellsTracking")
    sets = {r["first"]: set((r.get("second") or {}).get("m_idSet") or [])
            for r in body["m_elemIdSetMap"]}
    file_holders = {e for e, _c in holders["ExternalFileReferenceCell"]}
    assert file_holders and file_holders <= sets[1200]
    assert {i for i in sets[1200] if i in k1.ids} <= file_holders
    es_holders = {e for e, _c in holders["ESEntityCell"]}
    assert es_holders and es_holders <= sets[-100]


# ---------------------------------------------------------------------------
# 6. the emitted deliverables (built by the driver, certified on disk)
# ---------------------------------------------------------------------------

def _built(name: str) -> str:
    return os.path.join(ADDBACK, f"{name}.rvt")


@pytest.mark.parametrize("name", ["R1", "R1s", "R2", "R2s", "R3"])
def test_deliverable_validates_zero_errors(name):
    path = _built(name)
    if not os.path.exists(path):
        pytest.skip(f"{name}.rvt not built (run tools/genesis_addback.py)")
    v = GB.GT.validate(path)
    assert v["ok"] is True and v["errors"] == 0, f"{name}: {v.get('error_messages')}"


@pytest.mark.parametrize("name", ["R1", "R1s", "R2", "R2s"])
def test_deliverable_reports_are_coherent(name):
    j = os.path.join(ADDBACK, f"{name}.json")
    if not os.path.exists(j):
        pytest.skip(f"{name}.json not built")
    with open(j) as fh:
        rep = json.load(fh)
    assert rep["verdict"] == "VALID"
    cert = rep["certification"]
    assert cert["dangling_NEW_count"] == 0
    assert cert["validator"]["errors"] == 0
    # the file's document object matches K1's registry shape for its classes
    assert rep["self_parity_vs_K1"]["severity0"] == 0, rep["self_parity_vs_K1"]


def test_R2s_document_object_is_the_reference_verbatim():
    """R2s reinstates K1's Global/Latest byte-for-byte (the mechanics control)."""
    r2s = _built("R2s")
    if not (os.path.exists(r2s) and os.path.exists(K1)):
        pytest.skip("R2s / K1 not built")
    from rvt.container import open_rvt
    with open_rvt(K1) as f:
        a = f.inflate("Global/Latest", 0)
    with open_rvt(r2s) as f:
        b = f.inflate("Global/Latest", 0)
    assert a == b, "R2s must carry K1's document object verbatim"


def test_R2_repoints_every_substituted_row():
    j = os.path.join(ADDBACK, "R2.json")
    if not os.path.exists(j):
        pytest.skip("R2.json not built")
    with open(j) as fh:
        rep = json.load(fh)
    reg = next(s for s in rep["stages"] if s.get("stage") == "registries")
    rp = reg["repoint"]
    assert rp["map_size"] == 1348
    assert rp["leaves_rewritten"] == 1348          # exactly one reference per row
    assert "post_remap_purge" not in reg               # nothing left dangling to purge


def test_probes_manifest_names_the_one_thing_each_tests():
    p = os.path.join(ADDBACK, "probes.json")
    if not os.path.exists(p):
        pytest.skip("probes.json not built")
    with open(p) as fh:
        man = json.load(fh)
    files = [e for e in man["probes"] if e.get("file")]
    assert files, "manifest must list the probe files"
    for e in files:
        assert e["the_ONE_thing_it_tests"]
        assert e["passing_sibling"]
        assert e["if_PASS"] and e["if_FAIL"]
        assert e["validator"]["errors"] == 0
    assert "reading_the_results" in man


def test_parity_report_and_json_exist():
    md = os.path.join(ROOT, "docs", "writer", "registry-parity.md")
    j = os.path.join(ADDBACK, "registry_parity.json")
    if not (os.path.exists(md) and os.path.exists(j)):
        pytest.skip("parity outputs not built")
    with open(j) as fh:
        par = json.load(fh)
    assert par["label_ref"] == "K1" and par["label_subj"] == "S5"
    txt = open(md).read()
    for section in ("Ranked MISMATCHES", "UniqueElementsTracking",
                    "SymbolIdMgr.m_defElementTypeMap", "ElemsSetWithCellsTracking"):
        assert section in txt
    # the audit's key structural facts about the two documents
    ct = par["category_tracking"]["gstyleData"]
    assert ct["builtin_keys_missing_in_subj"] == 0
    assert ct["S5_present_gstyle_rows_NOT_indexed"] == 0

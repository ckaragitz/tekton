"""GENESIS-2 (tools/genesis_assemble.py, part 2): OUR ADocument.

Covers the schema-typed dangling-id purge engine, the registry maps
derived from the samples, the inventory extracted from OUR content, the
three authoring modes, and the end-to-end G1 stage.  Everything that needs
real files (samples / the assembled G0.rvt) is skipped when they are
absent; the pure pieces run on the house-standard catalog alone.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
TOOL = os.path.join(ROOT, "tools", "genesis_assemble.py")
G0 = os.path.join(ROOT, "experiments", "genesis", "G0.rvt")
MAPS = os.path.join(ROOT, "experiments", "genesis", "G1_registry_maps.json")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

needs_g0 = pytest.mark.skipif(not os.path.exists(G0), reason="needs experiments/genesis/G0.rvt")
needs_maps = pytest.mark.skipif(not (os.path.exists(MAPS) and os.path.exists(RST)),
                                reason="needs G1_registry_maps.json + rst sample")


@pytest.fixture(scope="module")
def ga():
    spec = importlib.util.spec_from_file_location("genesis_assemble", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["genesis_assemble"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def maps(ga):
    if os.path.exists(MAPS):
        with open(MAPS) as fh:
            return json.load(fh)
    if not os.path.exists(RST):
        pytest.skip("no registry maps and no samples to derive them from")
    return ga.derive_registry_maps(verbose=False)


@pytest.fixture(scope="module")
def content(ga):
    return ga.build_our_content(1_500_000)


@pytest.fixture(scope="module")
def inventory(ga, content, maps):
    return ga.derive_inventory(content, maps)


# ---------------------------------------------------------------------------
# registry maps (derived semantics, cross-sample stable)
# ---------------------------------------------------------------------------

@needs_maps
def test_registry_maps_have_the_stable_singleton_positions(maps):
    uet = maps["UET_POS_TO_CLASS"]
    # the singleton positions our skeleton fills — verified 72/72 across samples
    assert uet.get("2") == "ProjectInfo"
    assert uet.get("59") == "ElectricalSetting"
    assert uet.get("74") == "AllProjectPhases"
    assert uet.get("66") == "CableTraySizesElem"
    assert uet.get("67") == "ConduitSizesElem"
    # the parallel arrays the purge must NULL rather than shift
    par = maps["PARALLEL_GROUPS"]
    assert ["m_categoryIds", "m_ids"] in par.get("CategoryToIdMap", [])
    assert ["m_paramSetKeys", "m_paramSets"] in par.get("SymbolIdMgr", [])
    # the conductor custom-element data types (from the MEP sample)
    cells = set(maps["CUSTOM_ELEMENT_DATATYPE_GUID_TO_CELL"].values())
    assert {"RbsConductorMaterial", "RbsConductorTemperatureRating",
            "RbsConductorInsulationMaterial", "RbsConductorSize"} <= cells


# ---------------------------------------------------------------------------
# the inventory extracted from OUR content (no files needed)
# ---------------------------------------------------------------------------

@needs_maps
def test_inventory_extracts_the_registry_facts(ga, content, inventory):
    inv = inventory
    assert len(inv.ids) == len(content.elements)
    # every graphic-style / category row is one of ours and keys to our data
    assert len(inv.gstyle_rows) == len(inv.by_class["GStyleElem"])
    assert len(inv.category_rows) == len(inv.by_class["CategoryElem"])
    assert all(r["m_gstyleId"] in inv.ids for r in inv.gstyle_rows)
    # two levels, each with its plan view
    assert set(inv.level_plan_views) == set(inv.by_class["Level"])
    assert sum(len(v) for v in inv.level_plan_views.values()) == len(inv.by_class["DBViewPlan"])
    # every sketch plane is owned by one of our views; suns / drawings ours
    assert len(inv.sketch_planes) == len(inv.by_class["SketchPlane"])
    assert all(sp in inv.ids and view in inv.ids for sp, view in inv.sketch_planes)
    assert set(inv.suns) == set(inv.by_class["SunAndShadowSettings"])
    assert set(inv.drawings) == set(inv.by_class["DBDrawing"])
    # the nine conductor cells map onto four data-type GUIDs
    assert sum(len(v) for v in inv.custom_element_types.values()) == len(inv.by_class["CustomElement"])
    assert inv.project_view in inv.ids and inv.units in inv.ids and inv.true_north in inv.ids
    assert set(inv.base_points) == set(inv.by_class["BasePoint"])


# ---------------------------------------------------------------------------
# the byte-level id scan
# ---------------------------------------------------------------------------

def test_byte_scan_finds_i64_windows(ga):
    ids = {123_456, 999_999}
    blob = b"\x00" * 5 + struct.pack("<q", 123_456) + b"xyz" + struct.pack("<q", 999_999) * 2
    r = ga.byte_scan_ids(blob, ids)
    assert r["hits"] == 3 and r["distinct"] == 2
    assert ga.byte_scan_ids(b"\x00" * 64, ids)["hits"] == 0


def test_string_census_flags_sample_names(ga):
    tree = {"a": ["FOUNDATION-2700", {"b": "liqi"}, "GEN wall"], "c": {"d": "Autodesk Revit"}}
    c = ga.tree_string_census(tree)
    assert c["sample_watchlist_hits"].get("FOUNDATION-2700") == 1
    assert c["sample_watchlist_hits"].get("liqi") == 1
    assert c["vendor_tokens"].get("autodesk") == 1
    assert ga.tree_string_census({"x": "GEN 120", "y": ["our project"]})["sample_watchlist_hits"] == {}


# ---------------------------------------------------------------------------
# the purge engine + the authoring modes on the REAL document object
# ---------------------------------------------------------------------------

@needs_g0
@needs_maps
def test_purge_and_author_candidate_on_g0(ga, content, inventory, maps):
    """Decode G0's ADocument (the rst sample's, ~6,400 dangling ids), author
    the candidate: zero ElementId-typed dangling references remain, our ids
    are indexed, the sample name caches are gone, and the payload we would
    write re-decodes to exactly the tree we authored."""
    from rvt import adocument as adoc
    from rvt.container import open_rvt
    with open_rvt(G0) as f:
        payload = f.inflate(adoc.STREAM, 0)
    src = adoc.decode_latest(payload)
    assert src.clean
    live = ga._live_ids_of(G0)
    if live != set(inventory.ids):
        pytest.skip("G0.rvt on disk was built from a different content revision")
    tree, report = ga.author_adocument(src.value, inventory, maps, "candidate")
    ed = ga.AdocGraphEditor(maps=maps)
    # (1) zero dangling ElementId-typed leaves in every AppInfo body
    for cls_name, body in ga._appinfo_bodies(tree):
        assert ed.dangling_ids(body, cls_name, live) == [], cls_name
    # (2) our elements ARE indexed now (they were invisible in G0)
    refd = set(adoc.decode_latest(adoc.encode_latest(tree)).element_ids()) & live
    assert len(refd) >= 200, f"only {len(refd)} of our ids indexed"
    # (3) the loaded-content registry matches the empty ContentDocuments
    assert (tree["m_oContentTable"]["value"]["m_ContentRecSet"]) == []
    # (4) the sample's naming registries are empty
    nin = ga._appinfo_body(tree, "NewItemNumber")
    assert nin["m_items"] == []
    census = ga.tree_string_census(tree)
    assert not census["sample_watchlist_hits"], census["sample_watchlist_hits"]
    # (5) the "saved by" list is the product constant, not the sample lineage
    assert [x["m_str"] for x in tree["m_storedByRevitBuild"]] == [ga.PRODUCT_BUILD_STRING_2026]
    # (6) round-trip: encode -> decode == the tree we authored
    back = adoc.decode_latest(adoc.encode_latest(tree))
    assert back.clean and back.value == tree
    # (7) the report accounts for what happened
    assert report["purge"]["totals"]["dangling"] > 5000
    assert report["postconditions"]["dangling_after"] == 0
    assert report["forge_corpus"]["action"] == "CARRIED"          # flagged residual


@needs_g0
@needs_maps
def test_positional_registries_keep_their_shape(ga, content, inventory, maps):
    """UniqueElementsTracking is a positional table: same length after
    authoring, our singletons at the stable positions, -1 elsewhere; the
    CategoryToIdMap parallel arrays stay parallel."""
    from rvt import adocument as adoc
    from rvt.container import open_rvt
    with open_rvt(G0) as f:
        payload = f.inflate(adoc.STREAM, 0)
    src = adoc.decode_latest(payload)
    if ga._live_ids_of(G0) != set(inventory.ids):
        pytest.skip("G0.rvt on disk was built from a different content revision")
    before = ga._appinfo_body(copy.deepcopy(src.value), "UniqueElementsTracking")["m_elemIds"]
    tree, _ = ga.author_adocument(src.value, inventory, maps, "candidate")
    after = ga._appinfo_body(tree, "UniqueElementsTracking")["m_elemIds"]
    assert len(after) == len(before)
    assert after[2] == inventory.first_of("ProjectInfo")
    assert after[59] == inventory.first_of("ElectricalSetting")
    assert after[74] == inventory.first_of("AllProjectPhases")
    assert all(v == -1 or v in inventory.ids for v in after)
    sim = ga._appinfo_body(tree, "SymbolIdMgr")
    cm = sim["m_defCatSymIds"]["value"]
    assert len(cm["m_categoryIds"]) == len(cm["m_ids"])
    assert all(v == -1 for v in cm["m_ids"])          # no default family symbols of ours


@needs_g0
@needs_maps
def test_maxsafety_only_purges_and_maxpurity_drops_the_corpus(ga, content, inventory, maps):
    from rvt import adocument as adoc
    from rvt.container import open_rvt
    with open_rvt(G0) as f:
        payload = f.inflate(adoc.STREAM, 0)
    src = adoc.decode_latest(payload)
    if ga._live_ids_of(G0) != set(inventory.ids):
        pytest.skip("G0.rvt on disk was built from a different content revision")
    safe_tree, safe_rep = ga.author_adocument(src.value, inventory, maps, "maxsafety")
    pure_tree, pure_rep = ga.author_adocument(src.value, inventory, maps, "maxpurity")
    # max-safety: purge + coherence only; the corpus and the build lineage stay
    assert safe_rep["registries"]["m_storedByRevitBuild"].startswith("KEPT")
    assert safe_rep["forge_corpus"]["action"] == "CARRIED"
    es = ga._appinfo_body(safe_tree, "ESSchemaStorage")
    assert len(es["m_storedForgeSchemas"]) > 800
    assert safe_tree["m_oContentTable"]["value"]["m_ContentRecSet"] == []   # coherence in ALL modes
    # max-purity: the corpora are gone, our honest build string, no add-in names
    esp = ga._appinfo_body(pure_tree, "ESSchemaStorage")
    assert esp["m_storedForgeSchemas"] == [] and esp["m_storedParameterSchemas"] == []
    assert [x["m_str"] for x in pure_tree["m_storedByRevitBuild"]] == [ga.OUR_BUILD_STRING]
    assert pure_rep["forge_corpus"]["action"] == "EMPTIED"
    # both re-encode / re-decode identically
    for t in (safe_tree, pure_tree):
        back = adoc.decode_latest(adoc.encode_latest(t))
        assert back.clean and back.value == t


def test_positive_pid_detection(ga):
    """Safety net input: subtrees holding archive-indexed (positive pid)
    objects are recognised (the purge never drops such an element)."""
    assert ga._holds_positive_pid({"ptr_class": "X", "pid": 5, "value": {}})
    assert ga._holds_positive_pid([{"k": {"ptr_class": "Y", "pid": 7, "value": None}}])
    assert not ga._holds_positive_pid({"ptr_class": "X", "pid": -1, "value": {"a": [1, 2]}})
    assert not ga._holds_positive_pid({"first": 3, "second": {"m_elemIdSet": [10, 11]}})


@needs_g0
@needs_maps
def test_stage_writes_a_valid_candidate(tmp_path, ga, content, inventory, maps):
    """End-to-end: the emitted file re-opens, its ADocument decodes 100 %,
    it validates with zero errors, and the byte scan finds no sample id."""
    if ga._live_ids_of(G0) != set(inventory.ids):
        pytest.skip("G0.rvt on disk was built from a different content revision")
    out = str(tmp_path / "G1_candidate.rvt")
    rec = ga.stage_own_latest(G0, out, "candidate", inventory, maps, str(tmp_path))
    assert rec["self_decode_ok"] is True
    assert rec["byte_scan"]["sample_ids_after"]["hits"] <= 3      # coincidence windows only
    assert rec["byte_scan"]["our_ids_after"]["distinct"] >= 200
    v = ga.run_validator(out)
    assert v["ok"] and v["errors"] == 0, v["error_messages"]
    from rvt.adocument import open_document_object
    back = open_document_object(out)
    assert back.clean
    assert rec["element_id_refs_after"] >= rec["our_ids_referenced_after"] >= 200

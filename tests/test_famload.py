"""tests for rvt.famload (the embedded family-document loader) + rvt.famgen.heads
(our twelve annotation-head families).

Fast surface (G1_candidate is a 234-element file: a full load + verify runs
in < 2 s).  The rst basic sample is used read-only (census / dry run).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import famload as FL                     # noqa: E402
from rvt.famgen import heads as H                # noqa: E402

RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
G1 = os.path.join(ROOT, "experiments", "genesis", "G1_candidate.rvt")

pytestmark = pytest.mark.skipif(not (os.path.exists(RST) and os.path.exists(G1)),
                                reason="corpus / genesis base missing")


# ---------------------------------------------------------------------------
# the twelve head families
# ---------------------------------------------------------------------------

def test_head_specs_complete():
    assert len(H.HEAD_SPECS) == 12
    cats = {s.category for s in H.HEAD_SPECS.values()}
    assert cats == {H.OST_SECTION_HEADS, H.OST_LEVEL_HEADS, H.OST_GRID_HEADS,
                    H.OST_CALLOUT_HEADS, H.OST_ELEVATION_MARKS, H.OST_VIEW_TITLES,
                    H.OST_BOUNDARY_CONDITIONS}
    for key, spec in H.HEAD_SPECS.items():
        assert spec.key == key
        for bad in ("M_", "Autodesk"):
            assert bad not in spec.name and bad not in spec.type_name


def test_every_head_builds_and_roundtrips():
    for key in H.HEAD_SPECS:
        doc = H.build_head_family(key, start_id=900000)
        assert doc.finalized
        assert doc.category_id == H.HEAD_SPECS[key].category
        assert doc.part_type == H.PART_TYPE_ANNOTATION
        assert min(e.elem_id for e in doc.elements) == 900000
        # one type, the spec's parameters
        assert len(doc.types) == 1
        assert len(doc.by_class("ParamElemFamily")) == len(H.HEAD_SPECS[key].params)
        rt = doc.roundtrip()
        assert rt["failed"] == 0 and rt["roundtrip_ok"] == rt["records"] == 3 * len(doc.elements)


def test_head_embedded_unit_contract():
    doc = H.build_head_family("level_head", start_id=900000)
    u = doc.to_embedded_unit()
    assert str(u["content_doc_guid"]) == str(doc.document_guid)
    assert int(u["record_count"]) == len(doc.elements)
    assert u["type_names"] == ["Level Head - Circle"]
    # the self-Family carries our parameters and its absorbed-index table
    sf = doc.self_family
    fids = sf.obj["m_familyIds"]["value"]["m_data"]
    assert len(fids) == len(doc.elements) - 1
    caps = sorted(pe.refs.get("caption") for pe in doc.params.values())
    assert caps == ["Elevation", "Name", "Radius"]


def test_head_rfa_emission_valid(tmp_path):
    rep = H.emit_head_rfas(str(tmp_path), keys=["grid_head"])
    e = rep["families"]["grid_head"]
    p = os.path.join(ROOT, e["rfa"]["path"]) if not os.path.isabs(e["rfa"]["path"]) \
        else e["rfa"]["path"]
    if not os.path.exists(p):
        p = os.path.join(str(tmp_path), "head_grid_head.rfa")
    assert os.path.exists(p) and os.path.getsize(p) > 100_000
    assert e["roundtrip"]["failed"] == 0
    vf = e.get("validate_family") or {}
    assert vf.get("verdict") == "VALID" and vf.get("errors") == 0
    assert json.load(open(os.path.join(str(tmp_path), "heads_report.json")))


# ---------------------------------------------------------------------------
# the four-registry census
# ---------------------------------------------------------------------------

def test_census_sample_coherent():
    c = FL.four_registry_census(RST)
    assert c["save_units"] == 53
    assert c["contentdocs_entries"] == 52
    assert c["contenttable_records"] == 52
    assert len(c["familymgr_guids"]) == 52
    assert c["coherent"] is True and c["coherent_counts"] and c["coherent_guids"]
    assert not c["units_missing_from_contentdocs"]
    assert not c["units_missing_from_contenttable"]
    assert not c["units_missing_from_familymgr"]


def test_census_genesis_base_coherent_empty():
    c = FL.four_registry_census(G1)
    assert (c["save_units"], c["contentdocs_entries"],
            c["contenttable_records"], c["familymgr_entries"]) == (1, 0, 0, 0)
    assert c["coherent"] is True


# ---------------------------------------------------------------------------
# the loader
# ---------------------------------------------------------------------------

def test_dry_run_plan_and_gate_on_sample():
    res = FL.load_family_documents(RST, [H.family_load("level_head")], None)
    assert res.out_path is None and "dry run" in res.stop_reason
    host = res.proofs["host"]
    assert host["registries_before"]["coherent"] is True
    (plan,) = res.proofs["plans"]
    assert plan["doc_id_range"][0] > host["watermark"]
    assert plan["host_family_id"] > plan["doc_id_range"][1]
    assert plan["unit_records"] == 21
    assert len(plan["twin_of"]) == 3
    gate = res.proofs["roundtrip_gate"]
    assert gate["failed"] == 0 and gate["roundtrip_ok"] == gate["records"] == 21
    emb = res.proofs["embedded"]["level_head"]
    assert emb["adocument_self_check"]["decodes_clean"] is True
    assert emb["adocument_self_check"]["roundtrip_equal"] is True
    assert emb["save_unit"]["records"] == 21


def test_load_one_head_into_genesis_base(tmp_path):
    out = str(tmp_path / "g1_levelhead.rvt")
    rps = [FL.UsageRepoint("LevelAttributes", "m_familyTagId", "level_head",
                           only_if_set=False)]
    res = FL.load_family_documents(G1, [H.family_load("level_head")], out,
                                   repoints=rps)
    assert res.ok, json.dumps(res.proofs.get("verify_written"), default=str)[:2000]
    ver = res.proofs["verify_written"]
    reg = ver["registries"]
    assert (reg["save_units"], reg["contentdocs_entries"],
            reg["contenttable_records"], reg["familymgr_entries"]) == (2, 1, 1, 1)
    assert reg["coherent"] is True and reg["ours_in_all_four"] is True
    assert reg["units_added"] == 1 and reg["units_added_ok"] is True
    assert ver["container"]["crc_failures"] == 0
    assert ver["container"]["ecc_mismatches"] == 0
    assert ver["container"]["walker_errors"] == 0
    assert ver["container"]["stamps_ok"] is True
    assert not ver["container"]["host_records_missing"]
    assert ver["elemtable"]["our_host_ids_present"] is True
    assert ver["elemtable"]["watermark_covers_documents"] is True
    assert ver["host_linkage"]["ok"] is True
    assert ver["family_inventory"]["ok"] is True
    assert ver["validate"]["verdict"] == "VALID" and ver["validate"]["n_errors"] == 0
    # the usage field was repointed at our symbol (from -1)
    rr = res.proofs["pass3_usage_repoint"]
    assert rr["written"] is True
    (plan,) = res.plans
    assert any(e.get("symbol") == plan.symbol_id and e.get("ok") for e in rr["edits"])
    # read back: LevelAttributes.m_familyTagId == our symbol, deletion updated
    from rvt.mutate import Document
    d = Document.from_file(out)
    (la,) = d.ids_of_class("LevelAttributes")
    v = d.value(la)
    assert v["m_familyTagId"] == plan.symbol_id
    hdr = d.decode(la, 101).value
    dele = ((hdr.get("m_parents") or {}).get("value") or {}).get("m_deletion")
    assert plan.symbol_id in dele
    # our host Family names our content GUID; symbol -> family
    fam = d.value(plan.host_family_id)
    fd = ((fam.get("m_oFamDoc") or {}).get("value") or {})
    assert str(fd.get("m_contentDocGUID")) == plan.guid
    assert fam.get("m_name") == "RW Level Head - Circle"
    assert fam.get("m_surrogateId") == plan.surrogate_id
    sym = d.value(plan.symbol_id)
    assert sym.get("m_familyId") == plan.host_family_id
    assert sym.get("m_partitionSurrogateId") == plan.symbol_surrogate_id
    assert ((sym.get("m_symbolInfo") or {}).get("value") or {}).get("m_name") == "Level Head - Circle"


def test_load_several_heads_registries_move_together(tmp_path):
    out = str(tmp_path / "g1_three.rvt")
    keys = ["grid_head", "view_title", "boundary_condition"]
    res = FL.load_family_documents(G1, H.all_family_loads(keys), out)
    assert res.ok
    reg = res.proofs["verify_written"]["registries"]
    assert (reg["save_units"], reg["contentdocs_entries"],
            reg["contenttable_records"], reg["familymgr_entries"]) == (4, 3, 3, 3)
    assert reg["coherent"] and reg["ours_in_all_four"] and reg["units_added"] == 3
    # independent census agrees
    c = FL.four_registry_census(out)
    assert c["coherent"] is True
    guids = {p.guid.lower() for p in res.plans}
    assert guids <= set(c["unit_guids"])
    assert guids <= set(c["contentdocs_guids"])
    assert guids <= set(c["contenttable_guids"])
    assert guids <= set(c["familymgr_guids"])
    # ids are disjoint per family and above the base watermark, twins present
    ids = [i for p in res.plans for i in p.host_ids()]
    assert len(ids) == len(set(ids))
    assert min(ids) > res.proofs["host"]["watermark"]
    assert res.proofs["host_elements"]["count"] == sum(
        len(p.host_ids()) for p in res.plans)


def test_usage_repoint_only_if_set_semantics(tmp_path):
    out = str(tmp_path / "g1_noset.rvt")
    # G1's LevelAttributes.m_familyTagId is -1: only_if_set=True must SKIP it
    rps = [FL.UsageRepoint("LevelAttributes", "m_familyTagId", "level_head",
                           only_if_set=True)]
    res = FL.load_family_documents(G1, [H.family_load("level_head")], out,
                                   repoints=rps)
    assert res.ok
    rr = res.proofs.get("pass3_usage_repoint") or {}
    assert rr.get("written") is False
    assert any(e.get("skipped") for e in rr.get("edits", []))
    from rvt.mutate import Document
    d = Document.from_file(out)
    (la,) = d.ids_of_class("LevelAttributes")
    assert d.value(la)["m_familyTagId"] == -1
    # the family is still loaded (coherent, unreferenced)
    c = FL.four_registry_census(out)
    assert (c["save_units"], c["contentdocs_entries"],
            c["contenttable_records"], c["familymgr_entries"]) == (2, 1, 1, 1)
    assert c["coherent"] is True


def test_loader_refuses_ids_below_watermark(tmp_path):
    doc = H.build_head_family("callout_head", start_id=100)   # far below any watermark
    with pytest.raises(FL.LoaderError):
        FL.load_family_documents(G1, [FL.FamilyLoad(key="low", doc=doc)],
                                  str(tmp_path / "x.rvt"))


def test_family_load_and_default_repoints():
    fl = H.family_load("section_tail_filled")
    assert isinstance(fl, FL.FamilyLoad) and callable(fl.builder)
    doc = fl.builder(start_id=800000)
    assert doc.name == "RW Section Tail - Filled" and doc.category_id == H.OST_SECTION_HEADS
    rps = H.default_repoints(["level_head", "view_title"])
    keys = {r.family_key for r in rps}
    assert keys == {"level_head", "view_title"}
    classes = {r.referrer_class for r in rps}
    assert classes == {"LevelAttributes", "ViewportAttributes"}

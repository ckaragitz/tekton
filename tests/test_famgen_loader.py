"""Tests for rvt.famgen.loader -- L4/L5: loading a generated family into a
project (host Family / FamilySymbol / instance + ADocument registrations).

Fast tests share one dry-run authoring pass (no file); one module-scoped
fixture performs a REAL load into a copy of the rme sample and validates it.
"""
from __future__ import annotations

import json
import os
import uuid

import pytest

from rvt.famgen import loader as L
from rvt.famgen import factory as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

pytestmark = pytest.mark.skipif(not os.path.exists(HOST),
                                reason="rme sample project not present")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def host():
    return L.survey_host(HOST)


@pytest.fixture(scope="module")
def product(host):
    return F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                            spaces=42, voltage="480Y/277", mcb=True,
                            mounting="surface", solid=True,
                            start_id=host.watermark + 1)


@pytest.fixture(scope="module")
def dry(product):
    """One dry-run authoring pass (no file): plan + all host records +
    roundtrip gate + embedded ADocument + save unit + ADocument edits +
    ContentDocuments insert."""
    return L.load_family_into_project(HOST, out_path=None, product=product,
                                      place=True, symbol_solid=True, validate=False)


@pytest.fixture(scope="module")
def written(tmp_path_factory, host):
    """A REAL load into a copy of the host, validated (the heavy one)."""
    out = str(tmp_path_factory.mktemp("loader") / "project_with_generated_panel.rvt")
    prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                            spaces=42, voltage="480Y/277", mcb=True,
                            mounting="surface", solid=True,
                            start_id=host.watermark + 1)
    res = L.load_family_into_project(HOST, out, prod, place=True,
                                     symbol_solid=True, validate=True)
    return res


# ---------------------------------------------------------------------------
# host survey / plan
# ---------------------------------------------------------------------------

def test_survey_resolves_host_resources_by_rule(host):
    assert host.watermark >= 888013
    assert host.partition_name.startswith("Partitions/")
    # the Electrical Equipment category's projection GStyle = 124 on rme
    assert host.category == L.CAT_ELECTRICAL_EQUIPMENT
    assert host.category_gstyle == 124
    # the host's named load classifications include 'Power'
    assert host.load_classifications.get("Power") == 638830
    # a specimen instance of the category exists for placement scaffolding
    assert host.template_instance != L.INVALID


def test_plan_allocates_above_watermark_and_twins_every_param(product, host, dry):
    plan = dry.plan
    assert plan.guid == product.doc.document_guid
    lo = min(e.elem_id for e in product.doc.elements)
    assert lo > host.watermark
    # every top-level ParamElemFamily gets a host twin
    n_params = sum(1 for e in product.doc.elements if e.class_name == "ParamElemFamily")
    assert n_params == 14
    assert len(plan.twin_of) == n_params
    # host ids all above our document's own ids
    assert min(plan.twin_of.values()) > max(e.elem_id for e in product.doc.elements)
    assert plan.host_family_id > 0 and plan.symbol_id > 0 and plan.instance_id > 0
    ids = [plan.host_family_id, plan.surrogate_id, plan.symbol_id,
           plan.symbol_surrogate_id, plan.instance_id] + list(plan.twin_of.values())
    assert len(set(ids)) == len(ids)                     # all distinct
    # load classification resolved BY NAME
    assert plan.load_class_name == "Power" and plan.load_class_host == 638830
    assert 124 in plan.core_ids and 638830 in plan.core_ids


def test_dry_run_authors_and_gates_everything(dry):
    p = dry.proofs
    gate = p["roundtrip_gate"]
    # 19 elements x 3 seqs, every record encodes+decodes byte-exact
    assert gate["failed"] == 0 and gate["records"] == 57
    assert gate["roundtrip_ok"] == gate["records"]
    assert p["embedded_adocument"]["decodes_clean"] and p["embedded_adocument"]["roundtrip_equal"]
    assert p["adocument_reencode"]["clean"] is True
    cd = p["content_documents"]
    assert cd["entries_after"] == cd["entries_before"] + 1
    assert cd["ours_present"] and cd["end_record_intact"]
    assert dry.out_path is None and "dry run" in dry.stop_reason


def test_elements_are_the_full_load_set(dry):
    classes = [e["class"] for e in dry.elements]
    assert classes.count("ParamElemFamily") == 14
    for c in ("Family", "FamilySurrogate", "FamilySymbol", "FamSymSurrogate",
              "FamilyInstance"):
        assert classes.count(c) == 1, c
    reps = {e["class"]: e["rep"] for e in dry.elements if e["class"] != "ParamElemFamily"}
    assert reps["FamilySymbol"] == "GElement"       # our symbol solid (F4a)
    assert reps["FamilyInstance"] == "GElement"     # GInstance -> symbol
    assert reps["Family"] == "SerializedDummy"


# ---------------------------------------------------------------------------
# the individual host records (structure)
# ---------------------------------------------------------------------------

def test_host_family_is_our_self_family_transformed(product, host):
    plan = L.plan_load(product, host, place=True)
    el = L.author_host_family(product, plan, host)
    o = el.obj
    assert el.class_name == "Family" and el.elem_id == plan.host_family_id
    assert o["m_name"] == plan.family_name and o["m_name"]        # host carries the name
    assert o["m_famDocGUID"] == plan.fam_doc_guid
    assert o["m_surrogateId"] == plan.surrogate_id
    fd = o["m_oFamDoc"]
    assert fd["ptr_class"] == "FamilyDocument" and fd["pid"] == 3   # registered, pid 3
    assert fd["value"]["m_contentDocGUID"] == plan.guid
    b2s = fd["value"]["m_big2SmallMap2"]
    assert len(b2s) == 14
    # pairs are (host twin -> embedded param), sorted by host id
    assert [p["first"] for p in b2s] == sorted(p["first"] for p in b2s)
    assert {p["second"]["m_id64"] for p in b2s} == set(plan.twin_of.keys())
    assert fd["value"]["m_coreIds"] == plan.core_ids
    # familyIds: host twins keep the embedded absorbed index
    fids = o["m_familyIds"]["value"]["m_data"]
    for e in fids:
        emb = next(pp for pp, tt in plan.twin_of.items() if tt == e["m_elementId"])
        assert e["m_index"] == plan.abs_index[emb]
    # type table: leading blank ' ' row + our type
    pairs = o["m_pFamilyTypes"]["value"]["m_pairs"]
    assert pairs[0]["name"] == " " and len(pairs) == 2
    # ConnectorDataCell added ahead of the parameter order cell
    cells = [c["ptr_class"] for c in o["m_cellList"]["value"]["m_cells"]]
    assert cells[0] == "ConnectorDataCell" and "FamilyParamsOrderCell" in cells
    # host-only members present, family-doc-only state dropped
    assert o["m_dbviewInfos"] and o["m_oFamilyReferenceIdxMgr"] is not None
    # D3 corpus law: the host Family carries a (possibly empty) FamDimConstrMgr
    # in 831/831 specimens — never null (instbug-fix, WF_fix-certified form)
    fdc = o["m_oFamDimConstrMgr"]
    assert fdc is not None and fdc.get("ptr_class") == "FamDimConstrMgrImpl"
    assert o["m_fsdos"] == [] and o["m_refs"] == []
    assert o["m_path"] == ""
    # no family-document param id survives on the host record
    txt = json.dumps(o)
    assert not any(f'"m_paramId": {pid}' in txt for pid in plan.twin_of.keys())


def test_param_twins_are_ours_with_four_rewrites(product, host):
    plan = L.plan_load(product, host, place=True)
    twins = L.author_param_twins(product, plan)
    assert len(twins) == 14
    for t in twins:
        assert t.owner_id == plan.host_family_id
        assert t.obj["m_famId"] == plan.host_family_id
        pd = t.obj["m_pParamDef"]["value"]
        assert pd["m_paramElemId"] == t.elem_id == t.obj["m_id"]
        tid = pd["m_typeId"]["m_typeId"]
        assert tid.startswith("revit.local.family:" + plan.session_guid_hex)
        assert tid.endswith(f"{t.elem_id:08x}-1.0.0")
        assert t.header["m_familyId"] == plan.host_family_id


def test_surrogates_carry_the_format_constants(product, host):
    plan = L.plan_load(product, host, place=True)
    fs = L.author_family_surrogate(plan, host.category)
    assert fs.obj["m_elemId"] == plan.host_family_id
    assert fs.obj["m_guid"]["m_guid"] == L.SURROGATE_GUID
    assert fs.obj["m_previewElemId"] == -1
    assert fs.obj["m_name"] == plan.family_name
    ss = L.author_famsym_surrogate(plan, host.category)
    assert ss.obj["m_elemId"] == plan.symbol_id
    assert ss.obj["m_famSurrogateId"] == plan.surrogate_id
    assert ss.obj["m_name"] == plan.type_name


def test_symbol_geometry_id_space_is_self_consistent(product, host):
    plan = L.plan_load(product, host, place=True)
    form = L._form_bundle(product)
    ai = plan.abs_index[form.elem_id]
    geo = L.build_symbol_geometry(product, plan, host, absorbed_form_index=ai)
    step = geo["geom_steps"]["value"]["m_bRepFormGList"][0]["value"]
    fh = step["m_faceHistTable"]
    eh = step["m_edgeHistTable"]
    ch = step["m_curveHistTableSet"]
    faces = [e for e in fh if e["m_faceHist"]["m_keys"][0] == L.HIST_FACE]
    nodes = [e for e in fh if e["m_faceHist"]["m_keys"][0] == L.HIST_NODE]
    assert len(faces) == 6 and len(eh) == 12 and len(ch) == 1 and len(nodes) == 2
    # every face / edge entry names OUR extrusion's absorbed index
    assert all(e["m_faceHist"]["m_keys"][2] == ai for e in faces)
    assert all(e["m_edgeHist"]["m_keys"][2] == ai for e in eh)
    assert ch[0]["m_curveHist"]["m_keys"] == [L.HIST_FORM, ai, -1, -1, -1]
    # the ids form one flat space 0..N-1 and the GeomTable covers all of it
    ids = ({e["m_id"] for e in fh} | {e["m_id"] for e in eh} | {ch[0]["m_id"]})
    n = geo["n_symbol_ids"]
    assert ids == set(range(n))
    assert len(geo["geom_table"]["value"]["m_table"]) == n
    # face/edge symbol ids appear as the solid's GInfo tags
    rep = geo["rep"]
    solid = rep["m_subNodes"][0]["value"]["m_subNodes"][0]["value"]
    ftags = {f["value"]["m_GInfo"]["m_tag"] for f in solid["m_pFaces"]}
    assert ftags == {e["m_id"] for e in faces}
    assert solid["m_geometryTag"] == ch[0]["m_id"]
    # root GInfo = the category GStyle + the symbol id
    assert rep["m_GInfo"]["m_categoryId"] == host.category_gstyle
    assert rep["m_GInfo"]["m_tag"] == plan.symbol_id
    assert rep["m_elementId"] == plan.symbol_id
    # the symbol bbox is our TRUE panel box (20 in wide, 60 in tall, 5.75 in deep)
    lo, hi = geo["bbox"]
    assert abs((hi[0] - lo[0]) - 20 / 12) < 1e-6
    assert abs((hi[1] - lo[1]) - 60 / 12) < 1e-6
    assert abs((hi[2] - lo[2]) - 5.75 / 12) < 1e-6


def test_dummy_symbol_variant_has_no_geometry(product, host):
    plan = L.plan_load(product, host, place=False)
    rows = L._type_rows(product)
    el, geo = L.author_family_symbol(product, plan, host, rows, solid=False)
    assert geo is None and el.rep is None
    assert el.obj["m_geomSteps"] is None and el.obj["m_pGeomTable"] is None
    assert el.obj["m_symbolInfo"]["value"]["m_name"] == plan.type_name
    assert el.obj["m_familyId"] == plan.host_family_id


def test_instance_targets_our_symbol_and_rebuilds_connectors(product, host):
    plan = L.plan_load(product, host, place=True)
    fi = L.author_family_instance(product, plan, host)
    ii = fi.obj["m_pInstanceInfo"]["value"]
    assert ii["m_symbolId"] == plan.symbol_id
    assert fi.obj["m_masterSymbolId"] == plan.symbol_id      # symbol == master
    slots = fi.obj["m_pConnectorManager"]["value"]["m_connPtrArray"]
    assert len(slots) == 1                                   # OUR one connector
    assert slots[0]["value"]["m_arrRefs"] == []             # placed unconnected
    assert fi.rep is not None and fi.rep["m_elementId"] == fi.elem_id
    for n in fi.rep["m_subNodes"]:
        info = (n.get("value") or {}).get("m_instanceInfo", {}).get("value") or {}
        if info:
            assert info["m_symbolId"] == plan.symbol_id


def test_adocument_registrations_on_the_real_host(product, host):
    from rvt.container import open_rvt
    from rvt.adocument import decode_latest, encode_latest
    plan = L.plan_load(product, host, place=True)
    with open_rvt(HOST) as f:
        payload = f.inflate("Global/Latest")
    lat = decode_latest(payload)
    assert lat.clean
    import copy
    v = copy.deepcopy(lat.value)
    n_ct = len(v["m_oContentTable"]["value"]["m_ContentRecSet"])
    rep = L.register_in_host_adocument(v, plan, category=host.category, unit_records=41)
    assert rep["content_table_records"] == n_ct + 1
    ours = [r for r in v["m_oContentTable"]["value"]["m_ContentRecSet"]
            if r["m_ContentKey"]["m_guidKey"] == plan.guid]
    assert len(ours) == 1 and ours[0]["m_EpisodeCounts"][0]["second"] == 41
    fm = L._appinfo_slot(v, "FamilyMgr")
    ent = [e for e in fm["m_arrLoadedFamilyInfo"] if plan.guid in e["m_familyDocGUIDs"]]
    assert len(ent) == 1 and ent[0]["m_surrogateId"] == plan.surrogate_id
    etd = L._appinfo_slot(v, "ElementTrackingData")
    srow = next(r for r in etd["m_symbols"] if r["m_categoryId"] == host.category)
    assert plan.symbol_id in srow["m_elemIdSet"]
    assert srow["m_elemIdSet"] == sorted(srow["m_elemIdSet"])
    erow = next(r for r in etd["m_elems"] if r["m_categoryId"] == host.category)
    assert plan.instance_id in erow["m_elemIdSet"]
    # and the edited tree re-encodes and decodes clean
    back = decode_latest(encode_latest(v, trailer=lat.trailer))
    assert back.clean


# ---------------------------------------------------------------------------
# the REAL load (one file, validated)
# ---------------------------------------------------------------------------

def test_load_writes_a_valid_project_with_our_family(written):
    res = written
    assert res.ok, json.dumps(res.proofs.get("verify_written"), default=str)[:2000]
    v = res.proofs["verify_written"]
    # container health (validator structure layer = authoritative ECC gate)
    # + walker + our unit landed
    assert v["container"]["crc_failures"] == 0
    assert v["structure_layer"]["n_errors"] == 0
    assert v["structure_layer"]["verdict"] == "VALID"
    assert v["container"]["walker_errors"] == 0
    assert not v["partition"]["walker_errors"]
    assert v["partition"]["our_unit_index"] is not None
    # ElemTable knows our host ids
    assert v["elemtable"]["our_host_ids_present"] is True
    # the host ADocument carries our three registrations
    ad = v["adocument"]
    assert ad["clean"] and ad["content_table_record"] and ad["family_mgr_entry"]
    assert ad["symbol_tracked"]
    # our family is a real loaded host Family, keyed by our GUID
    fd = v["family_documents"]
    assert fd["ok"] and len(fd["ours"]) == 1
    ours = fd["ours"][0]
    assert ours["family_id"] == res.plan.host_family_id
    assert ours["family_name"] == res.plan.family_name
    assert ours["big2small_count"] == 14 and ours["n_types"] == 1
    assert ours["symbols"][0]["symbol_id"] == res.plan.symbol_id
    assert ours["n_records"] == 41
    # the placed instance references our symbol (symbol == master)
    assert v["instance"]["ok"] and v["instance"]["symbol_id"] == res.plan.symbol_id
    # provenance of what the load added is clean (host is the sample)
    assert v["provenance_ours"]["ok"] is True
    assert v["provenance_ours"]["suspects"]["our_unit"] == []
    assert v["provenance_ours"]["suspects"]["host_elements"] == []
    # THE GATE: rvt_validate 0 errors on the loaded project
    assert v["validate"]["n_errors"] == 0, v["validate"]["errors"]


def test_loaded_project_is_placeable_by_the_standard_api(written):
    """The brief's route: on the loaded project the standard
    ``rvt.mutate.Document.add_family_instance`` works on our NEW symbol
    (cloning our placed instance as its template)."""
    from rvt.mutate import Document
    res = written
    doc = Document.from_file(res.out_path)
    mine = [s for s in doc.symbols() if s["symbol_id"] == res.plan.symbol_id]
    assert len(mine) == 1
    assert mine[0]["family_id"] == res.plan.host_family_id
    assert mine[0]["symbol_name"] == res.plan.type_name
    assert doc.category_of(res.plan.symbol_id) == L.CAT_ELECTRICAL_EQUIPMENT
    fi = doc.add_family_instance(symbol_id=res.plan.symbol_id,
                                 level_id=doc.levels()[0]["id"],
                                 position=(75.0, 108.5, 17.8),
                                 host_id=res.proofs["plan"]["resolved"]["template_host"])
    ii = fi.obj["m_pInstanceInfo"]["value"]
    assert ii["m_symbolId"] == res.plan.symbol_id
    assert fi.obj["m_masterSymbolId"] == res.plan.symbol_id
    assert fi.template_id == res.plan.instance_id      # cloned OUR instance

"""Tests for rvt.famgen.factory -- the ASSET FACTORY (facts -> family -> .rfa)
and the project-side LOADER mechanisms.

Evidence tiers:

1. FACTS RESOLUTION: catalog facts drive the dimensions / ratings, every
   value carries its provenance, unsourced or out-of-catalog requests raise
   (never a fabricated dimension).
2. COMPOSITION: the generated family documents carry the tagging-contract
   parameter NAMES with correct values / units, enclosure geometry at the
   TRUE catalog dimensions, and connectors hosted on a real solid FACE
   (geometry tag + edge-loop tags) with parameter associations.
3. DELIVERY: a generated panelboard ``.rfa`` reads back clean, validates
   with 0 errors (family mode) and passes the provenance scan (no
   Autodesk / manufacturer content strings; our PartAtom / BasicFileInfo;
   the carried Formats/Latest is the corpus schema constant).
4. LOADER MECHANISMS: the ``Global/ContentDocuments`` codec is byte-exact
   on the corpus (parse -> assemble) and inserts an entry at its sorted
   position; our family save unit assembles and splices into a host
   partition stream walker-clean; our embedded ADocument authors and
   round-trips through the codec.

Corpus-dependent tests skip when the samples / schema are absent.
"""
from __future__ import annotations

import os
import struct

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                   "racbasicsamplefamily-2026.rfa")
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
HAVE_RFA = os.path.exists(RFA)
HAVE_RME = os.path.exists(RME)
HAVE_RST = os.path.exists(RST)
HAVE_SCHEMA = os.path.exists(os.path.join(
    ROOT, "extracted", "racbasicsampleproject", "Formats__Latest.gz", "000.bin")) \
    or HAVE_RFA

from rvt.famgen import factory as F                            # noqa: E402
from rvt.famgen import skeleton as SK                           # noqa: E402
from rvt.famgen import geometry as G                            # noqa: E402

needs_rfa = pytest.mark.skipif(not (HAVE_RFA and HAVE_SCHEMA),
                               reason="sample .rfa / schema absent")
needs_rme = pytest.mark.skipif(not HAVE_RME, reason="rme sample absent")
needs_schema = pytest.mark.skipif(not HAVE_SCHEMA, reason="schema absent")


# ---------------------------------------------------------------------------
# 1. facts resolution
# ---------------------------------------------------------------------------

def test_voltage_parsing():
    assert F._voltage_number("480Y/277") == (480.0, 3, 4)
    assert F._voltage_number("208Y/120") == (208.0, 3, 4)
    assert F._voltage_number("120/240") == (240.0, 1, 3)
    assert F._voltage_number(600) == (600.0, 3, 3)
    with pytest.raises(F.FactoryError):
        F._voltage_number("banana")


def test_panelboard_facts_dimensions_and_provenance():
    fs = F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                     voltage="480Y/277", mcb=True, mounting="surface")
    # width / depth are catalog FACTS (Eaton 20.00 W x 5.75 D box family)
    assert fs.get("width_in") == 20.0 and fs.values["width_in"].kind == "fact"
    assert fs.get("depth_in") == 5.75 and fs.values["depth_in"].kind == "fact"
    # PRL2X (480Y/277) height comes from the SHARED box family's PRL1X table
    # -> flagged assumed (surfaced), 400 A / 42 ckt / main breaker -> 60 in
    assert fs.variant == "PRL2X"
    assert fs.get("height_in") == 60.0
    assert fs.values["height_in"].kind == "assumed"
    assert "height_in" in fs.assumed()
    assert fs.get("voltage_ll_v") == 480.0
    assert fs.get("phases") == 3 and fs.get("wires") == 4
    assert fs.get("mains_type") == "MCB"
    assert fs.get("manufacturer") == "Eaton" and fs.get("model") == "PRL2X"


def test_panelboard_facts_prl1x_height_is_a_fact():
    fs = F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=225, spaces=30,
                                     voltage="208Y/120", mcb=False)
    assert fs.variant == "PRL1X"
    # 225 A main lugs, 30 circuits -> 48.00 in row (a table fact)
    assert fs.get("height_in") == 48.0
    assert fs.values["height_in"].kind == "fact"


def test_panelboard_more_than_42_spaces_is_multi_section_and_refused():
    with pytest.raises(F.FactoryError, match="42"):
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=84,
                                    voltage="480Y/277", mcb=True)


def test_panelboard_unknown_line_refused():
    with pytest.raises(F.FactoryError):
        F.resolve_panelboard_facts("acme", "widgets", mains_a=100, spaces=18,
                                    voltage="208Y/120")


def test_panelboard_second_vendor_square_d_nq():
    """The generic circuits->height lookup covers the Square D NQ table
    shape too (a second vendor proves the facts generalisation)."""
    fs = F.resolve_panelboard_facts("square-d", "nq", mains_a=225, spaces=42,
                                     voltage="120/240", mcb=False)
    assert fs.variant == "NQ"
    assert fs.get("width_in") == 20.0 and fs.get("depth_in") == 5.75
    assert fs.get("height_in") == 38.0                    # 42 spaces -> 38 in row (fact)
    assert fs.values["height_in"].kind == "fact"
    assert fs.get("manufacturer") == "Schneider Electric"
    # MCB / more circuits: the record's table is the MLO single-phase one ->
    # the height is flagged assumed (scope note), not silently trusted
    fs2 = F.resolve_panelboard_facts("square-d", "nq", mains_a=400, spaces=54,
                                      voltage="120/240", mcb=True)
    assert fs2.get("height_in") == 56.0
    assert fs2.values["height_in"].kind == "assumed"
    assert "MLO" in fs2.values["height_in"].note


def test_transformer_facts_are_catalog_dimensions():
    fs = F.resolve_transformer_facts(75, primary_v=480, secondary_v="208Y/120")
    assert fs.variant == "V48M28T7516"
    # frame FR942: 30.50 W x 43.00 H x 24.00 D in, 570 lb (facts)
    assert fs.get("width_in") == 30.5 and fs.values["width_in"].kind == "fact"
    assert fs.get("height_in") == 43.0
    assert fs.get("depth_in") == 24.0
    assert fs.get("weight_lb") == 570
    assert fs.get("frame") == "FR942"
    assert fs.get("kva") == 75.0


def test_transformer_500kva_dims_not_published_never_invented():
    with pytest.raises(F.FactoryError):
        F.resolve_transformer_facts(500)


def test_luminaire_troffer_facts():
    fs = F.resolve_luminaire_facts("recessed-troffer", size="2x4")
    # 2BLT4: 47.75 L x 23.75 W x 2.375 H in (distributor-read facts)
    assert fs.get("length_in") == 47.75 and fs.values["length_in"].kind == "fact"
    assert fs.get("width_in") == 23.75
    assert fs.get("height_in") == 2.375
    assert fs.get("wattage_w") == 38.0
    assert fs.get("shape") == "box"
    assert "http" in (fs.get("photometry_url") or "")     # URL reference, no file


def test_luminaire_downlight_housing_is_ours_not_fabricated():
    fs = F.resolve_luminaire_facts("downlight")
    # the LDN6 record has NULL housing dims -> OUR parametric can, never a fact
    assert fs.get("shape") == "cylinder"
    assert fs.values["can_diameter_in"].kind == "ours"
    assert fs.values["height_in"].kind == "ours"
    assert all(f.kind != "fact" for k, f in fs.values.items()
               if k in ("can_diameter_in", "height_in"))


def test_unknown_luminaire_kind_refused():
    with pytest.raises(F.FactoryError):
        F.resolve_luminaire_facts("gobo")


# ---------------------------------------------------------------------------
# 2. composition
# ---------------------------------------------------------------------------

@needs_schema
def test_panelboard_family_composition():
    prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                              spaces=42, voltage="480Y/277", mcb=True,
                              mounting="surface")
    doc = prod.doc
    assert prod.kind == "panelboard" and doc.finalized
    assert doc.category_id == SK.OST_ELECTRICAL_EQUIPMENT
    assert doc.part_type == SK.PART_TYPE["panelboard"] == 14
    assert doc.work_plane_based is True
    # the tagging-contract parameter NAMES are present
    for pname, _s, _g in F.PANEL_CONTRACT_PARAMS:
        assert pname in doc.params, f"contract parameter {pname} missing"
    for dim in ("Width", "Height", "Depth"):
        assert dim in doc.params
    # one type, values in internal units
    assert len(doc.types) == 1
    tname, vals = doc.types[0]
    assert "400A" in tname and "MCB" in tname
    W, H, D = doc.params["Width"], doc.params["Height"], doc.params["Depth"]
    assert vals[W.elem_id] == pytest.approx(20.0 / 12)
    assert vals[H.elem_id] == pytest.approx(60.0 / 12)
    assert vals[D.elem_id] == pytest.approx(5.75 / 12)
    assert vals[doc.params["Voltage"].elem_id] == pytest.approx(SK.volts(480))
    assert vals[doc.params["Phases"].elem_id] == 3
    assert vals[doc.params["Wires"].elem_id] == 4
    assert vals[doc.params["NumberOfCircuits"].elem_id] == 42
    assert vals[doc.params["MainsType"].elem_id] == "MCB"
    # identity built-ins resolve to the type BIP ids
    assert vals[SK.BIP_TYPE_MANUFACTURER] == "Eaton"
    assert vals[SK.BIP_TYPE_MODEL] == "PRL2X"
    # geometry: one box at the true catalog dims
    assert len(prod.forms) == 1
    fp = prod.forms[0].params
    assert fp["width_ft"] == pytest.approx(20.0 / 12)
    assert fp["depth_ft"] == pytest.approx(60.0 / 12)   # H along family Y
    assert fp["height_ft"] == pytest.approx(5.75 / 12)  # depth extruded +Z
    # connector: hosted on the enclosure's +y (top) face = tag 2, edge tags
    # [3, 4, 8, 17] -- the real panelboard's convention
    assert len(doc.connectors) == 1
    con = doc.connectors[0].obj
    gr = con["m_oPlaneRef"]["value"]["m_geomRef"]
    ext = prod.forms[0].by_class("ExtrusionElem")[0]
    assert gr["m_elemId"] == ext.elem_id and gr["m_geomTag"] == 2
    assert con["m_oEdgeLoopRef"]["value"]["m_sortedTagArr"] == [3, 4, 8, 17]
    dom = con["m_pDomain"]["value"]
    assert dom["m_dVoltage"] == pytest.approx(SK.volts(480))
    assert dom["m_nNumberOfPoles"] == 3
    # voltage associated to the Voltage family parameter
    cells = con["m_cellList"]["value"]["m_cells"]
    binding = next(c for c in cells
                   if c.get("ptr_class") == "FamilyParametrizedElemParamsCell")
    driven = binding["value"]["m_paramDrivenData"]
    assert (doc.params["Voltage"].elem_id, SK.ELEM_PROP_VOLTAGE) in [
        (d["m_famParamId"], d["m_elemPropId"]) for d in driven]


@needs_schema
def test_box_face_tags_match_the_specimen_convention():
    assert F.box_face("+y")["tag"] == 2
    assert F.box_face("+y")["edges"] == [3, 4, 8, 17]
    assert F.box_face("top")["tag"] == 1
    assert F.box_face("top")["edges"] == [3, 6, 10, 14]
    assert F.box_face("bottom")["tag"] == 0
    with pytest.raises(KeyError):
        F.box_face("diagonal")


@needs_schema
def test_transformer_family_composition():
    prod = F.make_transformer(kva=75, primary_v=480, secondary_v="208Y/120")
    doc = prod.doc
    assert doc.part_type == SK.PART_TYPE["electrical_equipment"] == 15
    assert doc.work_plane_based is False
    assert len(doc.connectors) == 2
    volts = sorted(round(c.obj["m_pDomain"]["value"]["m_dVoltage"] * 0.3048 ** 2)
                   for c in doc.connectors)
    assert volts == [208, 480]                              # secondary, primary
    fp = prod.forms[0].params
    assert fp["width_ft"] == pytest.approx(30.5 / 12)
    assert fp["depth_ft"] == pytest.approx(24.0 / 12)
    assert fp["height_ft"] == pytest.approx(43.0 / 12)
    # both connectors on the TOP face (tag 1)
    for c in doc.connectors:
        assert c.obj["m_oPlaneRef"]["value"]["m_geomRef"]["m_geomTag"] == 1


@needs_schema
def test_luminaire_family_composition():
    prod = F.make_luminaire(kind="recessed-troffer", size="2x4", wattage=38,
                            lumens=4600, cct=4000, voltage="120-277")
    doc = prod.doc
    assert doc.category_id == SK.OST_LIGHTING_FIXTURES
    assert doc.part_type == 0
    assert len(doc.connectors) == 1
    dom = doc.connectors[0].obj["m_pDomain"]["value"]
    assert round(dom["m_dVoltage"] * 0.3048 ** 2) == 120
    assert dom["m_nNumberOfPoles"] == 1
    fp = prod.forms[0].params
    assert fp["width_ft"] == pytest.approx(47.75 / 12)     # length along X
    assert fp["depth_ft"] == pytest.approx(23.75 / 12)
    assert fp["height_ft"] == pytest.approx(2.375 / 12)
    for pname in ("Wattage", "Lumens", "Color Temperature", "Voltage",
                  "IES File (URL reference)"):
        assert pname in doc.params
    _t, vals = doc.types[0]
    assert "http" in vals[doc.params["IES File (URL reference)"].elem_id]


@needs_schema
def test_composition_roundtrips_and_forms_a_closed_graph():
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="208Y/120", mcb=False)
    doc = prod.doc
    rt = doc.roundtrip()
    assert rt["roundtrip_ok"] == rt["records"] and rt["failed"] == 0
    # closed graph: every referenced id (deletion lists) is an element or a BIP
    ids = set(doc.element_ids())
    for e in doc.elements:
        dele = ((e.header.get("m_parents") or {}).get("value") or {}).get("m_deletion") or []
        for d in dele:
            assert d in ids or d < 0, f"{e.class_name} {e.elem_id}: dangling ref {d}"


# ---------------------------------------------------------------------------
# 3. delivery + provenance
# ---------------------------------------------------------------------------

@needs_rfa
def test_panelboard_rfa_verifies_validates_and_is_provenance_clean(tmp_path):
    prod = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400,
                              spaces=42, voltage="480Y/277", mcb=True)
    out = str(tmp_path / "panel.rfa")
    rep = prod.write(out, validate=True, provenance=True)
    assert rep["ok"], rep
    assert rep["verify"]["ok"] and rep["verify"]["gzip_crc_failures"] == 0
    assert rep["verify"]["ecc_mismatch"] == 0
    assert rep["verify"]["id_sets_identical_across_seqs"]
    st = rep["verify"]["decode_seq102"]
    assert st["clean"] == st["records"]
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0
    # v2 emission (docs/inbox/standalone.md P4): container from the bundled
    # genesis base, Global/Latest = OUR authored family ADocument -- the
    # provenance ledger is provenance_scan_v2, every check must hold
    prov = rep["provenance"]
    assert prov["ok"], prov.get("suspects")
    assert prov["suspects"] == []
    assert prov["checks"]["zero_dangling_element_refs"]
    assert prov["checks"]["zero_donor_id_byte_hits"]
    assert prov["checks"]["zero_donor_name_strings"]
    assert prov["checks"]["identity_is_ours"]
    assert prov["checks"]["formats_latest_is_format_constant"]
    assert rep["container_mode"] == "bundled-base"
    assert os.path.exists(rep["report_path"])


def test_provenance_scan_whitelists_forge_vocabulary_only():
    vocab = ["autodesk.spec.aec:length-1.0.0",
             "autodesk.parameter.group:dimensions-1.0.0",
             "autodesk.unit.symbol:ampere-1.0.1",
             "revit.local.family:abcd:12345678-1.0.0"]
    assert F._suspects(vocab) == []                      # format vocabulary is fine
    sus = F._suspects(["Autodesk Revit 2026", "C:\\Users\\liqi\\panel.rfa",
                      "OmniClass 23.40.20.14.17", "M_Table-End", "our text"])
    assert "our text" not in sus
    assert any("Autodesk" in s for s in sus)
    assert any("Users" in s for s in sus)
    assert any("OmniClass" in s for s in sus)


# ---------------------------------------------------------------------------
# 4. loader mechanisms
# ---------------------------------------------------------------------------

def _cd_payload(path):
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        return b"".join(f.inflate_all("Global/ContentDocuments"))


@needs_rme
def test_content_documents_codec_byte_exact_on_rme():
    cd = _cd_payload(RME)
    entries, tail = F.parse_content_documents(cd)
    assert len(entries) == 305
    assert tail == F.CD_END_RECORD
    assert F.assemble_content_documents(entries, tail=tail) == cd
    # every entry's ADocument leads with the ADocument class id 0x1c
    assert all(struct.unpack_from("<H", a, 0)[0] == 0x1C for _g, a in entries)


@pytest.mark.skipif(not HAVE_RST, reason="rst sample absent")
def test_content_documents_codec_byte_exact_on_rst():
    cd = _cd_payload(RST)
    entries, tail = F.parse_content_documents(cd)
    assert len(entries) == 52
    assert F.assemble_content_documents(entries, tail=tail) == cd


@needs_rme
def test_content_document_insert_sorted_and_reparse():
    cd = _cd_payload(RME)
    guid = "ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"
    adoc = b"\x1c\x00" + b"\xaa" * 100
    new = F.insert_content_document(cd, guid, adoc)
    entries2, tail2 = F.parse_content_documents(new)
    assert len(entries2) == 306
    assert (guid, adoc) in entries2
    assert tail2 == F.CD_END_RECORD
    assert len(new) - len(cd) == len(adoc) + 36
    with pytest.raises(ValueError):
        F.insert_content_document(new, guid, adoc)         # duplicate refused


@needs_schema
def test_embedded_adocument_authors_and_roundtrips():
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="208Y/120", mcb=False)
    ad = F.author_embedded_adocument(prod.doc)
    sc = ad["self_check"]
    assert sc["decodes_clean"] and sc["roundtrip_equal"]
    assert sc["elem_recs"] == len(prod.doc.elements)
    # entry form: ADocument class id, no trailer
    assert struct.unpack_from("<H", ad["payload"], 0)[0] == 0x1C
    v = ad["value"]
    # ownerFamilyId = our self-Family; embedded doc has no build strings
    assert v["m_ownerFamilyId"] == prod.doc.self_family.elem_id
    assert v["m_storedByRevitBuild"] == []
    et = v["m_elemTable"]["value"]
    assert len(et["m_elemArr"]) == len(prod.doc.elements)
    assert et["m_pSource"]["value"]["m_last"] == max(prod.doc.element_ids())
    # the open question is carried honestly
    assert "UNKNOWN" in sc["open_question"]


@needs_rme
def test_save_unit_builds_and_splices_walker_clean():
    from rvt.container import open_rvt
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="208Y/120", mcb=False,
                              start_id=2_000_000)
    unit = F.build_family_save_unit(prod.doc)
    assert unit["record_count"] == len(prod.doc.elements)
    assert unit["bytes"][:2] == struct.pack("<H", 0x3A3)   # separator lead
    with open_rvt(RME) as f:
        pn = f.partition_streams()[0]
        logical = f.logical(pn)
    sp = F.splice_save_unit(logical, unit["bytes"])
    w = sp["walker"]
    assert w["errors"] == []
    assert w["units_after"] == w["units_before"] + 1
    assert w["our_unit_guid"] == unit["guid"]
    assert w["our_unit_counter"] == unit["record_count"]
    assert w["id_sets_identical"]
    # each seq carries every element + the sentinel
    for s, n in w["our_unit_records"].items():
        assert n == len(prod.doc.elements) + 1
    assert len(sp["logical"]) == len(logical) + len(unit["bytes"])


@needs_rme
def test_loader_readiness_proofs_and_points_at_the_built_loader(tmp_path):
    out = str(tmp_path / "readiness.json")
    rep = F.loader_readiness(out_json=out)                  # fast: no emit
    assert rep["built_mechanisms_ok"] is True
    assert rep["project_file_emitted"] is False              # no emit requested
    p = rep["proofs"]
    assert p["P1_content_documents_roundtrip"]["byte_exact"]
    assert p["P2_entry_insert"]["ours_present"]
    assert p["P3_embedded_adocument"]["decodes_clean"]
    assert p["P4_partition_splice"]["id_sets_identical"]
    assert p["P5_id_allocation"]["above_watermark"]
    # L4 / L5 are now BUILT by rvt.famgen.loader
    assert rep["spec"]["L4_host_elements"]["status"].startswith("BUILT")
    assert rep["spec"]["L5_host_content_table"]["status"].startswith("BUILT")
    assert os.path.exists(out)

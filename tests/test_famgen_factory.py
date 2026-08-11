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

Composition and delivery need only a class schema, which a fresh clone / CI
has (``rvt.schema.load_schema()`` falls back to the bundled genesis base's
own ``Formats/Latest``); the loader-mechanism tests that read the sample
projects skip when ``samples/`` is absent.
"""
from __future__ import annotations

import json
import os
import struct
from functools import partial

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
HAVE_RME = os.path.exists(RME)
HAVE_RST = os.path.exists(RST)

from conftest import needs_schema                              # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.famgen import skeleton as SK                           # noqa: E402
from rvt.famgen import geometry as G                            # noqa: E402

needs_rme = pytest.mark.skipif(not HAVE_RME, reason="rme sample absent")


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
    # FREE-STANDING, not work-plane-based: the geometry stands W x D x H on
    # the reference level, and the hosting flag has to agree with it.  (The
    # Autodesk rme panelboard is work-plane-based and traces the panel FACE
    # in the family XY with the depth on Z -- which is why it lies flat in
    # the family editor and stands up only once placed on a wall face.  We
    # place instances on LEVELS, not by picking a face, so that combination
    # genuinely left the panel on the floor.)
    assert doc.work_plane_based is False
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
    # THE PANEL STANDS UP: W x D footprint, H tall (it used to trace W x H
    # in plan and push the depth up +Z, which laid a 5 ft panel on the floor)
    assert fp["width_ft"] == pytest.approx(20.0 / 12)
    assert fp["depth_ft"] == pytest.approx(5.75 / 12)   # D along family Y
    assert fp["height_ft"] == pytest.approx(60.0 / 12)  # H extruded +Z
    # connector: hosted on the enclosure's top face = tag 2, edge tags
    # [3, 4, 8, 17] -- the real panelboard's convention
    assert len(doc.connectors) == 1
    con = doc.connectors[0].obj
    gr = con["m_oPlaneRef"]["value"]["m_geomRef"]
    ext = prod.forms[0].by_class("ExtrusionElem")[0]
    # the feeder enters a STANDING panel from above, so the connector rides
    # the +z cap (tag 1, edges [3, 6, 10, 14]) -- the same face and tags the
    # transformer's connectors use.  It used to sit on +y, the face that
    # pointed up only because the panel was lying on its back.
    assert gr["m_elemId"] == ext.elem_id and gr["m_geomTag"] == 1
    assert con["m_oEdgeLoopRef"]["value"]["m_sortedTagArr"] == [3, 6, 10, 14]
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
    # the primary WINDING is the family's one primary connector; the secondary
    # books 75 kVA balanced over its 3 poles = 25 kVA per phase
    pri, sec = (c.obj["m_pDomain"]["value"] for c in doc.connectors)
    assert [(d["m_strConnectorDescription"], d["m_bIsConnectorPrimary"]) for d in (pri, sec)] == \
        [("Primary", True), ("Secondary", False)]
    assert [sec[f"m_dApparentLoadPhase{i}"] for i in (1, 2, 3)] == \
        pytest.approx([SK.voltamps(25000.0)] * 3)
    assert sec["m_dApparentLoad"] == 0.0 and sec["m_systemType"] == SK.ELECTRICAL_SYSTEM_POWER_UNBALANCED


def _rfa_connector_domains(path):
    """[(m_index, ConnectorElemDomainElectrical dict)] decoded from an .rfa FILE."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    vals = [idx.value(0, eid) for eid in sorted(idx.ids_of_class(0, "ConnectorElem"))]
    assert all(v["m_pDomain"]["ptr_class"] == "ConnectorElemDomainElectrical" for v in vals)
    return [(v["m_index"], v["m_pDomain"]["value"]) for v in vals]


@needs_schema
def test_emitted_transformer_rfa_decodes_three_equal_phase_loads_and_one_primary(tmp_path):
    """Fresh-clone law check ON THE FILE: the written 75 kVA transformer .rfa
    decodes back to a secondary with three equal per-phase loads (internal
    units = VA / 0.3048**2) and exactly one primary connector -- the primary
    winding.  (Family-mode VALID + provenance of this same default build:
    test_every_kind_writes_a_family_mode_valid_provenance_clean_rfa.)"""
    prod = F.make_transformer(kva=75, primary_v=480, secondary_v="208Y/120")
    rep = prod.write(str(tmp_path / "xfmr.rfa"), validate=False, provenance=False)
    doms = _rfa_connector_domains(rep["path"])
    assert [(i, d["m_bIsConnectorPrimary"], round(d["m_dVoltage"] * 0.3048 ** 2))
            for i, d in doms] == [(1, True, 480), (2, False, 208)]
    sec = doms[1][1]
    assert sec["m_nNumberOfPoles"] == 3 and sec["m_systemType"] == 31     # Power-Unbalanced
    per_phase = 75000.0 / 3 / 0.3048 ** 2                       # 269097.76 internal
    assert per_phase == pytest.approx(SK.voltamps(25000.0))
    assert [sec[f"m_dApparentLoadPhase{i}"] for i in (1, 2, 3)] == pytest.approx([per_phase] * 3)
    assert sec["m_dApparentLoad"] == 0.0


@needs_schema
def test_add_connector_allows_one_primary_per_family():
    """add_connector: the first connector is primary by default, later ones
    are not, and asking for a second primary raises."""
    doc = SK.new_family_document("electrical_equipment", "OnePrimary",
                                 part_type=SK.PART_TYPE["electrical_equipment"])
    fb = F.add_box_form(doc, 1.0, 1.0, 1.0, rep=G.REP_DUMMY)
    kw = dict(host=fb, face="top", location=(0, 0, 1.0), direction=(0, 0, 1), u_axis=(1, 0, 0),
              voltage_v=208, poles=3)
    a = F.add_connector(doc, **kw)
    b = F.add_connector(doc, **kw)
    with pytest.raises(F.FactoryError):
        F.add_connector(doc, primary=True, **kw)
    c = F.add_connector(doc, primary=False, **kw)
    flags = [x.obj["m_pDomain"]["value"]["m_bIsConnectorPrimary"] for x in (a, b, c)]
    assert flags == [True, False, False] and len(doc.connectors) == 3


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
    for pname in ("Wattage", "Luminous Flux", "Initial Color Temperature", "Voltage",
                  "IES File (URL reference)"):     # the lighting table's spelling (#622)
        assert pname in doc.params
    _t, vals = doc.types[0]
    assert "http" in vals[doc.params["IES File (URL reference)"].elem_id]


def test_device_facts_resolve_from_the_generic_record():
    """Issue #166: every device kind resolves from generic/devices-and-mounting;
    envelopes are 'assumed' and surfaced, the ADA reach envelope is the FACT,
    the mounting height defaults to the record's convention (18 receptacle /
    48 switch) unless given, and voltage / load are the job's ('given')."""
    rec = F.resolve_device_facts("duplex-receptacle")
    assert rec.variant == "duplex-receptacle-5-15R" and rec.catalog == "generic/devices-and-mounting"
    assert rec.get("mounting_height_in") == 18.0 and rec.values["mounting_height_in"].kind == "assumed"
    assert rec.get("ada_reach_range_in") == [15, 48] and rec.values["ada_reach_range_in"].kind == "fact"
    assert (rec.get("voltage_v"), rec.get("load_va")) == (120.0, 180.0)
    assert {rec.values[k].kind for k in ("voltage_v", "load_va")} == {"given"}
    assert "NEC 220.14(I)" in rec.values["load_va"].note
    for k in ("box_width_in", "box_height_in", "box_depth_in", "plate_width_in",
              "plate_height_in", "plate_thickness_in"):
        assert rec.get(k) > 0 and k in rec.assumed()
    assert rec.get("manufacturer") == "generic"
    sw = F.resolve_device_facts("switch")
    assert sw.variant == "toggle-switch-single-pole" and sw.get("mounting_height_in") == 48.0
    jb = F.resolve_device_facts("junction-box", mounting_height_in=96, voltage="277", va=0)
    assert jb.variant == "box-4in-square" and jb.get("mounting_height_in") == 96.0
    assert jb.values["mounting_height_in"].kind == "given" and jb.get("voltage_v") == 277.0
    assert (jb.get("box_width_in"), jb.get("box_depth_in")) == (4.0, 1.5)
    assert "box_width_in" not in jb.assumed()                # the 4 in square identity is a fact
    assert F.device_kind("outlet") == "duplex-receptacle" and F.device_kind("jbox") == "junction-box"
    with pytest.raises(F.FactoryError):
        F.resolve_device_facts("toaster")


@needs_schema
@pytest.mark.parametrize("kind,variant,height", [
    ("duplex-receptacle", "duplex-receptacle-5-15R", 18.0),
    ("switch", "toggle-switch-single-pole", 48.0),
    ("junction-box", "box-4in-square", 18.0)])
def test_device_family_composition(kind, variant, height):
    """make_device: an Electrical Fixtures work-plane family (no face-hosting
    claim) = faceplate proud of the wall face + device box recessed behind
    it, ONE 1-pole 120 V / 180 VA PRIMARY connector on the back of the box
    bound to Voltage / Apparent Load, Mounting Height from the facts, Manufacturer
    'generic' / Model = the record's member on the one type row."""
    prod = F.make_device(kind, standards=False)
    doc = prod.doc
    assert prod.kind == "device" and prod.facts.variant == variant
    assert doc.category_id == SK.OST_ELECTRICAL_FIXTURES and doc.part_type == 0
    assert doc.work_plane_based and doc.finalized
    # standards=False = the constructor's OWN parameters, nothing else (the
    # regression control for the category-standards layer, #601)
    assert sorted(doc.params) == ["Apparent Load", "Mounting Height", "Voltage"]   # the table's spelling (#622)
    assert prod.standards is None
    assert [f.kind for f in prod.forms] == ["plate", "box"]
    plate, box = prod.forms
    assert plate.params["base_z_ft"] == 0.0 and box.params["base_z_ft"] == pytest.approx(
        -prod.facts.get("box_depth_in") / 12)
    assert box.params["width_ft"] == pytest.approx(prod.facts.get("box_width_in") / 12)
    assert len(doc.connectors) == 1
    con = doc.connectors[0]
    dom = con.obj["m_pDomain"]["value"]
    assert dom["m_nNumberOfPoles"] == 1 and dom["m_bIsConnectorPrimary"] is True
    assert round(dom["m_dVoltage"] * 0.3048 ** 2) == 120
    assert dom["m_dApparentLoadPhase1"] == pytest.approx(SK.voltamps(180.0))
    assert dom["m_dApparentLoadPhase2"] == dom["m_dApparentLoadPhase3"] == dom["m_dApparentLoad"] == 0.0
    assert dom["m_systemType"] == 31
    assert any("bottom face" in n for n in con.notes)          # hosted on the back of the box
    (tname, vals), = doc.types
    assert vals[doc.params["Mounting Height"].elem_id] == pytest.approx(height / 12)
    ident = {bip: vals[bip] for bip in (SK.BIP_TYPE_MANUFACTURER, SK.BIP_TYPE_MODEL,
                                          SK.BIP_TYPE_DESCRIPTION)}
    assert ident[SK.BIP_TYPE_MANUFACTURER] == "generic"
    assert ident[SK.BIP_TYPE_MODEL] == variant
    assert "in AFF" in ident[SK.BIP_TYPE_DESCRIPTION] and "120V" in tname
    summ = prod.summary()
    assert summ["category"] == "Electrical Fixtures" and summ["connectors"] == 1
    assert "mounting_height_in" in summ["unverified_fields"]


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

@needs_schema
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


#: every product kind the ``make_family`` CLI advertises, with its defaults
ALL_KINDS = {
    "panelboard": F.make_panelboard,
    "transformer": F.make_transformer,
    "troffer": partial(F.make_luminaire, kind="recessed-troffer"),
    "downlight": partial(F.make_luminaire, kind="downlight"),
    "duplex-receptacle": partial(F.make_device, "duplex-receptacle"),
    "switch": partial(F.make_device, "switch"),
    "junction-box": partial(F.make_device, "junction-box"),
}


@needs_schema
@pytest.mark.parametrize("kind", sorted(ALL_KINDS))
def test_every_kind_writes_a_family_mode_valid_provenance_clean_rfa(tmp_path, kind):
    """Each advertised kind composes AND writes from the bundled base:
    read-back clean, family-mode VALID (0 errors), provenance ledger all
    green.  (Validator green is necessary, not certification -- rule 4.)"""
    prod = ALL_KINDS[kind]()
    assert prod.doc.finalized and len(prod.doc.connectors) >= 1
    rep = prod.write(str(tmp_path / f"{kind}.rfa"), validate=True, provenance=True)
    assert rep["ok"], rep.get("caveats")
    assert rep["verify"]["ok"], rep["verify"]
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0, fam.get("errors")
    prov = rep["provenance"]
    assert prov["ok"] and prov["suspects"] == [], prov.get("suspects")
    assert os.path.getsize(rep["path"]) > 100_000
    # on the FILE: exactly one primary connector per family, every connector
    # Power-Unbalanced (31) with its load per phase and m_dApparentLoad 0 (#164)
    doms = [d for _i, d in _rfa_connector_domains(rep["path"])]
    assert sum(d["m_bIsConnectorPrimary"] for d in doms) == 1 and doms[0]["m_bIsConnectorPrimary"]
    assert all(d["m_systemType"] == 31 and d["m_dApparentLoad"] == 0.0 for d in doms)


@needs_schema
def test_connector_refuses_a_host_that_is_not_a_4_curve_prism():
    """add_connector speaks box_face's _box_tags(4): a true two-arc cylinder
    host is refused, not silently mis-tagged."""
    doc = SK.new_family_document("lighting_fixture", "Guard", work_plane_based=True)
    ctx = F.geometry_context(doc)
    cyl = G.cylinder(0.25, 0.5, ctx, doc.ids)
    doc.add(*cyl.elements)
    with pytest.raises(F.FactoryError, match="4-curve prism"):
        F.add_connector(doc, host=cyl, face="top", location=(0, 0, 0.5),
                        direction=(1, 0, 0), u_axis=(0, 0, -1), voltage_v=120, poles=1)


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
# 3b. TYPE CATALOGS -- one family, N catalog selections (issue #163)
# ---------------------------------------------------------------------------

#: a multi-type build per advertised kind: (constructor kwargs, expected type names)
MULTI = {
    "panelboard": (dict(fn=F.make_panelboard, mains_a=400, spaces=42, voltage="480Y/277",
                        mcb=False, mounting="surface", types=[225, "400A", 600]),
                   ["225A MLO 42ckt", "400A MLO 42ckt", "600A MLO 42ckt"]),
    "transformer": (dict(fn=F.make_transformer, kva=75, types=[30, "45kVA", 75]),
                    ["30 kVA 480-208Y/120", "45 kVA 480-208Y/120", "75 kVA 480-208Y/120"]),
    "troffer": (dict(fn=F.make_luminaire, kind="recessed-troffer", size="2x4", cct=4000,
                     types=[30, 38, {"wattage": 48, "lumens": 6000}]),
                ["2x4 30W 4000K", "2x4 38W 4000K", "2x4 48W 4000K"]),
    "downlight": (dict(fn=F.make_luminaire, kind="downlight",
                       types=[{"lumens": 1000, "type_name": "6in 1000lm"},
                              {"lumens": 2000, "type_name": "6in 2000lm"}]),
                  ["6in 1000lm", "6in 2000lm"]),
}


def _multi(kind, **extra):
    kw = dict(MULTI[kind][0]); fn = kw.pop("fn")
    kw.update(extra)
    return fn(**kw)


def test_type_jobs_normalise_selectors():
    prim = {"mains_a": 400, "spaces": 42, "mcb": True}
    assert F._type_jobs(None, prim, scalar_key="mains_a") == [prim]
    assert F._type_jobs([], prim, scalar_key="mains_a") == [prim]
    jobs = F._type_jobs([225, "400A", {"mains_a": 600, "mcb": False, "type_name": "X"}],
                        prim, scalar_key="mains_a")
    assert [j["mains_a"] for j in jobs] == [225.0, 400.0, 600]
    assert jobs[2]["mcb"] is False and jobs[2]["type_name"] == "X" and jobs[0]["mcb"] is True
    with pytest.raises(F.FactoryError, match="per-type"):
        F._type_jobs([{"voltage": 208}], prim, scalar_key="mains_a")   # family-level, not per type
    with pytest.raises(F.FactoryError, match="not a number"):
        F._type_jobs(["big"], prim, scalar_key="mains_a")


@needs_schema
@pytest.mark.parametrize("kind", sorted(MULTI))
def test_multi_type_family_has_one_row_per_selection(kind):
    prod = _multi(kind)
    want = MULTI[kind][1]
    assert [n for n, _v in prod.doc.types] == want                    # the unit-side table
    assert [t.name for t in prod.types] == want
    summ = prod.summary()
    assert summ["types"] == want
    assert [t["name"] for t in summ["type_facts"]] == want
    # per-type facts ride in the report: each row has its own sheet + values
    for tf in summ["type_facts"]:
        assert set(tf) >= {"name", "subject", "variant", "assumed_fields", "values"}
    # nothing assumed hides in a row: the family-level list is the union
    union = sorted({a for t in prod.types for a in t.facts.assumed()})
    assert summ["assumed_fields"] == union
    # ONE solid, one connector set -- a product line, not N families
    assert len(prod.forms) == 1
    assert sum(1 for e in prod.doc.elements if e.class_name == "ExtrusionElem") == 1
    assert any("types" in n and "primary" in n for n in prod.notes)


@needs_schema
def test_multi_type_rows_carry_per_type_facts():
    """Per-type dims / ratings / Model as parameter VALUES: the 225/400/600 A
    PRL2X rows differ in Height (48/60/72 in, the sizing table) and
    MainsRating; the transformer rows differ in frame dims, weight AND Model."""
    prod = _multi("panelboard")
    pid = {n: pe.elem_id for n, pe in prod.doc.params.items()}
    heights = [round(vals[pid["Height"]] * 12.0, 3) for _n, vals in prod.doc.types]
    mains = [vals[pid["MainsRating"]] for _n, vals in prod.doc.types]
    assert heights == [48.0, 60.0, 72.0] and mains == [225.0, 400.0, 600.0]
    assert [t.facts.get("height_in") for t in prod.types] == [48.0, 60.0, 72.0]
    # the solid is the PRIMARY (first) type's box: 20 x 48 in profile
    assert prod.forms[0].params["dims_in"] == [20.0, 48.0, 5.75]
    x = _multi("transformer")
    models = [vals[SK._TYPE_TEXT_PARAMS["model"]] for _n, vals in x.doc.types]
    assert len(set(models)) == 3                                       # per-type Model
    widths = [t.facts.get("width_in") for t in x.types]
    assert widths[0] == widths[1] != widths[2]                          # FR940 / FR940 / FR942
    # the catalog rows carry the weight in lb (the type table converts it to kg, #630)
    assert [round(v["Operating Weight"]) for v in (t.as_json()["values"] for t in x.types)] == [409, 416, 570]


@needs_schema
def test_multi_type_family_name_drops_what_varies():
    assert _multi("panelboard").name == "Panelboard 480Y/277 MLO 42ckt Surface"
    assert _multi("transformer").name == "Dry Type Transformer 480-208Y/120"
    assert _multi("troffer").name == "Recessed Troffer 2x4"
    # file stems name the rating set
    assert _multi("panelboard").file_stem == "eaton_prl2x_225_400_600a_42sp_480y_277"
    assert _multi("transformer").file_stem == "xfmr_30_45_75kva_480_208y_120"


@needs_schema
def test_duplicate_type_names_refused():
    with pytest.raises(F.FactoryError, match="same type name"):
        F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", types=[400, 400])
    with pytest.raises(F.FactoryError, match="same type name"):
        F.make_luminaire(kind="downlight", types=[{"lumens": 1000}, {"lumens": 2000}])


@needs_schema
def test_default_single_type_structure_unchanged():
    """No ``types=`` == the historical single-type family, row for row: same
    name, stem, one type, same values as an explicit one-selector build."""
    a = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400, spaces=42,
                         voltage="480Y/277", mcb=True, mounting="surface")
    b = F.make_panelboard(vendor="eaton", line="pow-r-line", mains_a=400, spaces=42,
                         voltage="480Y/277", mcb=True, mounting="surface", types=[400])
    assert a.name == b.name == "Panelboard 480Y/277 400A MCB 42ckt Surface"
    assert a.file_stem == b.file_stem == "eaton_prl2x_400a_42sp_480y_277"
    assert [n for n, _v in a.doc.types] == [n for n, _v in b.doc.types] == ["400A MCB 42ckt"]
    assert [sorted(v.items(), key=str) for _n, v in a.doc.types] == \
        [sorted(v.items(), key=str) for _n, v in b.doc.types]
    assert [(e.elem_id, e.class_name) for e in a.doc.elements] == \
        [(e.elem_id, e.class_name) for e in b.doc.elements]
    assert len(a.types) == 1 and a.summary()["assumed_fields"] == a.facts.assumed()
    assert a.notes == b.notes


@needs_schema
def test_type_catalog_text_is_ours_one_row_per_type(tmp_path):
    prod = _multi("panelboard")
    txt = F.type_catalog_text(prod)
    lines = txt.split("\r\n")
    assert lines[-1] == "" and len(lines) == 1 + 3 + 1
    head = lines[0].split(",")
    assert head[0] == "" and all(h.count("##") == 2 for h in head[1:])   # ,Param##SPEC##UNITS
    assert "Width##LENGTH##INCHES" in head and "MainsRating##ELECTRICAL_CURRENT##AMPERES" in head
    assert "Model##OTHER##" in head and "Voltage##ELECTRICAL_POTENTIAL##VOLTS" in head
    rows = [l.split(",") for l in lines[1:4]]
    assert [r[0] for r in rows] == MULTI["panelboard"][1]
    hi = head.index("Height##LENGTH##INCHES"); mi = head.index("MainsRating##ELECTRICAL_CURRENT##AMPERES")
    assert [r[hi] for r in rows] == ["48", "60", "72"] and [r[mi] for r in rows] == ["225", "400", "600"]
    assert txt.isascii() and "Autodesk" not in txt
    rep = F.write_type_catalog(prod, str(tmp_path / "p.txt"))
    assert rep["columns"] == head[1:] and open(rep["path"], newline="").read() == txt
    assert F._catalog_cell(5.750) == "5.75" and F._catalog_cell(None) == ""
    # a value with a comma / quote is quoted by the csv writer, never split
    prod.types[0].catalog.append(("Note", "text", 'a,"b"'))
    assert F.type_catalog_text(prod).split("\r\n")[1].endswith(',"a,""b"""')


@needs_schema
def test_write_type_catalog_lands_beside_the_rfa_and_in_the_report(tmp_path):
    prod = _multi("transformer")
    assert prod.write_type_catalog(str(tmp_path / "t.rfa"))["path"] == str(tmp_path / "t.txt")
    rep = prod.write(str(tmp_path / "t.rfa"), validate=False, provenance=False)
    tc = rep["family"]["type_catalog"]
    assert tc["path"] == str(tmp_path / "t.txt") and os.path.isfile(tc["path"])
    assert tc["types"] == MULTI["transformer"][1] and "Operating Weight##MASS##POUNDS_MASS" in tc["columns"]
    import json as _json
    on_disk = _json.load(open(rep["report_path"]))
    assert on_disk["family"]["type_catalog"]["path"] == tc["path"]     # the sidecar report too


@needs_schema
@pytest.mark.parametrize("kind", sorted(MULTI))
def test_multi_type_rfa_is_valid_provenance_clean_and_inventories_n_types(tmp_path, kind):
    """The emitted multi-type .rfa: read-back clean, family-mode VALID 0
    errors, provenance green, and the convert package's inventory lists the
    N type names in order (validator green is necessary, not certification)."""
    from rvt.convert import modify_family as MF
    prod = _multi(kind)
    rep = prod.write(str(tmp_path / f"{kind}.rfa"), validate=True, provenance=True)
    assert rep["ok"], rep.get("caveats")
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0, fam.get("errors")
    assert rep["provenance"]["ok"] and rep["provenance"]["suspects"] == []
    assert [t["name"] for t in rep["family"]["type_facts"]] == MULTI[kind][1]
    inv = MF.inventory_family(rep["path"])
    assert inv.type_names == MULTI[kind][1]


@needs_schema
def test_scoped_edit_of_one_type_row_rereads(tmp_path):
    """`edit_family --set MainsRating=800 --type '600A MLO 42ckt'`: only that
    row changes; family-mode VALID; the engine's re-read gate holds."""
    from rvt.convert import edit_family as EF
    from rvt.families import FamilyIndex
    prod = _multi("panelboard")
    src = str(tmp_path / "p3.rfa")
    assert prod.write(src, validate=False, provenance=False)["verify"]["ok"]
    rc = EF.main([src, "-o", str(tmp_path / "e"), "--stem", "scoped",
                  "--set", "MainsRating=800", "--type", "600A MLO 42ckt"])
    assert rc == 0
    out = str(tmp_path / "e" / "scoped.rfa")
    idx = FamilyIndex(out)
    recs = idx.unit_records(0)[102]
    fam_id = [i for i, r in recs.items() if idx.class_name(r.class_id) == "Family"][0]
    ftt = idx.decode(0, fam_id, 102).value["m_pFamilyTypes"]["value"]
    pid = prod.doc.params["MainsRating"].elem_id
    got = [(p["name"], [r["m_value"] for r in p["params"]["m_params"]
                       if r.get("m_paramId") == pid][0]) for p in ftt["m_pairs"]]
    assert got == [("225A MLO 42ckt", 225.0), ("400A MLO 42ckt", 400.0), ("600A MLO 42ckt", 800.0)]


def test_make_family_cli_exposes_types(capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_family",
                                                  os.path.join(ROOT, "tools", "make_family.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod._types_arg("225, 400 ,600") == ["225", "400", "600"] and mod._types_arg(None) == []
    for sub in ("panelboard", "transformer", "luminaire"):
        with pytest.raises(SystemExit):
            mod.main([sub, "--help"])
        out = capsys.readouterr().out
        assert "--types" in out and "--type-catalog" in out and "--shared-params" in out


# ---------------------------------------------------------------------------
# 3c. SHARED parameters -- OUR file's GUIDs verbatim (issue #165)
# ---------------------------------------------------------------------------

#: OUR tracked shared-parameter file and its eleven rows (the tagging contract)
SHARED_FILE = F.DEFAULT_SHARED_PARAMS
CONTRACT_GUIDS = {
    "PanelName": "d2cce9ee-8e62-44ff-b5ab-12ead03922b8",
    "Voltage": "002b1533-731c-41b3-b1a5-20f6b1ee035a",
    "Phases": "1816cd3d-3644-40b9-8188-9f9bee361411",
    "Wires": "c3611f34-2603-40b9-8dc6-08a736656a6f",
    "BusRating": "ea6b58a3-d06a-43c6-82f2-83e88a5348e0",
    "MainsType": "65863827-d986-49c3-b257-4fcc1d7e8337",
    "MainsRating": "32a6688e-cda7-4884-b635-10e1ad2da190",
    "ShortCircuitRatingkA": "95713ca1-2c46-40a7-9e6e-ea3a59ca834f",
    "Mounting": "ea7d916a-5caf-4069-a3f1-5a5f6df75fba",
    "NumberOfCircuits": "9aeb45cc-a05e-4cd2-9f5d-fc101a841b3c",
    "NeutralRating": "0c2e8d22-6ff6-4049-b265-f93fae7afc64",
}
GEN_BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
needs_base = pytest.mark.skipif(not os.path.isfile(GEN_BASE), reason="bundled genesis base absent")


@needs_schema
def test_make_family_cli_device_verb_writes_a_valid_rfa(tmp_path, capsys):
    """`make_family.py device --kind K` = the fresh-clone deliverable: exit 0,
    family-mode VALID 0 errors, provenance clean, the connector decoding to
    1-pole / 120 V / 180 VA / primary on the FILE."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_family_cli_dev", os.path.join(ROOT, "tools", "make_family.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    out = tmp_path / "sw.rfa"
    assert cli.main(["device", "--kind", "switch", "--height", "44", "-o", str(out), "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["ok"] and rep["validate"]["family_mode"]["n_errors"] == 0 and rep["provenance"]["ok"]
    assert rep["family"]["category"] == "Electrical Fixtures"
    assert rep["family"]["type_facts"][0]["values"]["Mounting Height"] == 44.0
    (idx, dom), = _rfa_connector_domains(str(out))
    assert (dom["m_nNumberOfPoles"], round(dom["m_dVoltage"] * 0.3048 ** 2),
            round(dom["m_dApparentLoadPhase1"] * 0.3048 ** 2), dom["m_bIsConnectorPrimary"]) \
        == (1, 120, 180, True)
    with pytest.raises(SystemExit):                           # argparse: unknown --kind choice
        cli.main(["device", "--kind", "toaster", "-o", str(tmp_path / "t.rfa")])


def test_shared_parameter_file_parses_our_tracked_txt():
    """The documented tab-separated *PARAM grammar of OUR file: eleven rows,
    GUIDs verbatim, datatypes mapped to the factory's spec keys, group name
    resolved through the GROUP table -- exactly the panelboard contract."""
    assert os.path.isfile(SHARED_FILE)
    rows = SK.read_shared_parameter_file(SHARED_FILE)
    assert {n: r.guid for n, r in rows.items()} == CONTRACT_GUIDS
    assert list(rows) == [p[0] for p in F.PANEL_CONTRACT_PARAMS]             # file order = contract
    assert all(SK.shared_datatype_matches(rows[n].datatype, F.SPEC[s]) for n, s, _g in F.PANEL_CONTRACT_PARAMS)
    assert not SK.shared_datatype_matches("TEXT", F.SPEC["voltage"])
    assert all(r.group == "Panelboard" and r.visible for r in rows.values())
    assert rows["PanelName"].description == "Panel schedule name"


def test_shared_parameter_file_grammar_edges(tmp_path):
    """UTF-16 (Revit's own encoding) parses; a bad GUID / duplicate name /
    headerless row is a ValueError, never a silent skip."""
    txt = ("# This is a Revit shared parameter file.\r\n*META\tVERSION\tMINVERSION\r\nMETA\t2\t1\r\n"
           "*GROUP\tID\tNAME\r\nGROUP\t7\tOurs\r\n"
           "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\r\n"
           "PARAM\t0c2e8d22-6ff6-4049-b265-f93fae7afc64\tNeutralRating\tTEXT\t\t7\t1\r\n")
    p16 = tmp_path / "u16.txt"
    p16.write_bytes(txt.encode("utf-16"))                       # BOM + UTF-16 LE
    rows = SK.read_shared_parameter_file(str(p16))
    assert rows["NeutralRating"].guid == CONTRACT_GUIDS["NeutralRating"]
    assert rows["NeutralRating"].group == "Ours" and rows["NeutralRating"].description == ""
    bad = tmp_path / "bad.txt"
    bad.write_text(txt.replace("0c2e8d22-6ff6-4049-b265-f93fae7afc64", "not-a-guid"), encoding="utf-8")
    with pytest.raises(ValueError, match="GUID"):
        SK.read_shared_parameter_file(str(bad))
    dup = tmp_path / "dup.txt"
    dup.write_text(txt + txt.splitlines()[-1] + "\r\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        SK.read_shared_parameter_file(str(dup))
    nohdr = tmp_path / "nohdr.txt"
    nohdr.write_text("PARAM\tx\ty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        SK.read_shared_parameter_file(str(nohdr))


@needs_schema
def test_shared_params_flag_makes_the_eleven_contract_params_shared_rest_local():
    # standards=False: this test pins the SHARED-parameter mechanism, so the
    # family carries the constructor's own parameters and nothing else (the
    # category-standards layer is exercised by its own tests, #601)
    prod = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True,
                              shared_params=SHARED_FILE, standards=False)
    assert prod.shared_parameters() == CONTRACT_GUIDS
    assert prod.summary()["shared_parameters"] == CONTRACT_GUIDS
    classes = {n: pe.class_name for n, pe in prod.doc.params.items()}
    assert {n for n, c in classes.items() if c == "ParamElemExternal"} == set(CONTRACT_GUIDS)
    assert {n for n, c in classes.items() if c == "ParamElemFamily"} == {"Width", "Height", "Depth"}
    for name, guid in CONTRACT_GUIDS.items():
        o = prod.doc.params[name].obj
        assert o["m_externalParamKey"]["m_guidValue"] == guid
        assert o["m_pParamDef"]["value"]["m_typeId"]["m_typeId"] == SK.shared_param_type_id(guid)
    # type-table values still keyed by the (shared) element ids
    row = {e["m_paramId"]: e for e in
           prod.doc.self_family.obj["m_pFamilyTypes"]["value"]["m_pairs"][0]["params"]["m_params"]}
    assert row[prod.doc.params["PanelName"].elem_id]["m_str"] == "PANEL"
    assert row[prod.doc.params["NumberOfCircuits"].elem_id]["m_int"] == 42
    assert row[prod.doc.params["Voltage"].elem_id]["m_value"] == pytest.approx(SK.volts(480.0))
    assert any("11 SHARED parameters" in n and "no loads claim" in n for n in prod.notes)
    assert prod.doc.roundtrip()["failed"] == 0
    # parsed rows are accepted too; other products share only what matches by caption + datatype
    rows = SK.read_shared_parameter_file(SHARED_FILE)
    assert F.make_transformer(kva=75, shared_params=rows, standards=False).shared_parameters() == \
        {"Phases": CONTRACT_GUIDS["Phases"]}
    assert F.make_luminaire(wattage=38, lumens=4600, cct=4000, shared_params=rows,
                            standards=False).shared_parameters() \
        == {"Voltage": CONTRACT_GUIDS["Voltage"]}
    # ... and the CATEGORY STANDARDS (#601) go through the same promotion: a
    # transformer's standard Voltage / Wires / Mounting are the file's rows, so
    # they land SHARED at the file's GUIDs, while the panel-only schedule
    # parameters (PanelName, BusRating, NumberOfCircuits ...) are not on a
    # transformer at all -- the product set, not one category-wide list.
    xf = F.make_transformer(kva=75, shared_params=rows).shared_parameters()
    assert set(xf) == {"Phases", "Voltage", "Wires", "Mounting"}
    assert all(xf[n] == CONTRACT_GUIDS[n] for n in xf)
    assert not {"PanelName", "BusRating", "NumberOfCircuits"} & set(xf)
    # a datatype disagreement is refused, never papered over with a second GUID
    clash = dict(rows, Width=SK.SharedParamDef(guid=CONTRACT_GUIDS["PanelName"], name="Width",
                                              datatype="TEXT"))
    with pytest.raises(ValueError, match="DATATYPE"):
        F.make_panelboard(shared_params=clash)


@needs_schema
def test_default_build_has_no_shared_params_and_deterministic_local_identities():
    """No flag == the historical shape: every parameter a ParamElemFamily,
    same ids / classes / order as before; and two default builds now agree
    on every parameter identity (uuid5, not a per-build uuid4)."""
    a = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True)
    b = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True)
    assert a.shared_parameters() == {} and not any("SHARED" in n for n in a.notes)
    assert all(pe.class_name == "ParamElemFamily" for pe in a.doc.params.values())
    assert [(e.elem_id, e.class_name) for e in a.doc.elements] == \
        [(e.elem_id, e.class_name) for e in b.doc.elements]
    tids_a, tids_b = ([pe.obj["m_pParamDef"]["value"]["m_typeId"]["m_typeId"]
                       for pe in p.doc.params.values()] for p in (a, b))
    assert tids_a == tids_b
    assert tids_a[0] == SK.param_type_id(SK.local_param_guid(a.name, "Width"),
                                         a.doc.params["Width"].elem_id)


@needs_schema
def test_shared_panelboard_rfa_is_valid_clean_and_decodes_the_file_guids(tmp_path):
    """ON THE FILE, fresh-clone: the --shared-params panelboard writes from
    the bundled base, family-mode VALID 0 errors, provenance ledger all green
    ('revit.local.shared' is whitelisted format vocabulary), and the eleven
    ParamElemExternal records decode back GUID-for-GUID to OUR file."""
    from rvt.families import FamilyIndex
    prod = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True,
                              shared_params=SHARED_FILE, standards=False)
    rep = prod.write(str(tmp_path / "panel_shared.rfa"), validate=True, provenance=True)
    assert rep["ok"], rep.get("caveats")
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0, fam.get("errors")
    prov = rep["provenance"]
    assert prov["ok"] and prov["suspects"] == [], prov.get("suspects")
    assert rep["family"]["shared_parameters"] == CONTRACT_GUIDS
    idx = FamilyIndex(rep["path"])
    ext = [idx.value(0, eid) for eid in sorted(idx.ids_of_class(0, "ParamElemExternal"))]
    decoded = {v["m_pParamDef"]["value"]["m_caption"]: v["m_externalParamKey"]["m_guidValue"]
               for v in ext}
    assert decoded == CONTRACT_GUIDS
    assert all(v["m_pParamDef"]["value"]["m_typeId"]["m_typeId"]
               == SK.shared_param_type_id(v["m_externalParamKey"]["m_guidValue"]) for v in ext)
    assert len(idx.ids_of_class(0, "ParamElemFamily")) == 3           # Width / Height / Depth
    assert F._suspects(["revit.local.shared:d2cce9ee8e6244ffb5ab12ead03922b8-1.0.0"]) == []


@needs_base
def test_loader_twins_keep_the_shared_identity_verbatim():
    """Both loaders twin a ParamElemExternal as itself: id / owner rewritten
    like any twin, but the revit.local.shared typeId and the GUID key are the
    shared parameter's identity and are NOT re-minted (a local twin still
    takes the host session form)."""
    from rvt.frontdoor import standalone as SA
    from rvt.famgen import loader as L
    import rvt.famload as FL
    SA.install_schema(GEN_BASE)
    host = L.survey_host(GEN_BASE)
    prod = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True,
                              shared_params=SHARED_FILE, start_id=host.watermark + 1,
                              standards=False)
    plan = L.plan_load(prod, host, place=False)
    twins = L.author_param_twins(prod, plan)
    _assert_twins(twins, plan, prod.doc)
    # famload (the document loader) -- same law
    fhost = FL.survey_host(GEN_BASE)
    prod2 = F.make_panelboard(mains_a=400, spaces=42, voltage="480Y/277", mcb=True,
                               shared_params=SHARED_FILE, start_id=fhost.watermark + 1,
                               standards=False)
    fplan, _next = FL._plan_family(FL.FamilyLoad(key="p", doc=prod2.doc), prod2.doc, fhost,
                                   fhost.watermark + 1)
    _assert_twins(FL.author_param_twins(prod2.doc, fplan), fplan, prod2.doc)


def _assert_twins(twins, plan, doc):
    assert len(twins) == len(doc.params) == 14 and len(plan.twin_of) == 14
    assert sum(pe.class_name == "ParamElemExternal" for pe in doc.params.values()) == 11
    by_id = {t.elem_id: t for t in twins}
    for name, pe in doc.params.items():
        t = by_id[plan.twin_of[pe.elem_id]]
        pd = t.obj["m_pParamDef"]["value"]
        assert t.class_name == pe.class_name == t.header["m_classDef"]["m_ref"]["classref"]
        assert t.obj["m_id"] == pd["m_paramElemId"] == t.elem_id
        assert t.obj["m_famId"] == t.header["m_familyId"] == plan.host_family_id
        if pe.class_name == "ParamElemExternal":
            guid = CONTRACT_GUIDS[name]
            assert t.obj["m_externalParamKey"]["m_guidValue"] == guid
            assert pd["m_typeId"]["m_typeId"] == SK.shared_param_type_id(guid)
        else:
            assert pd["m_typeId"]["m_typeId"] == \
                f"revit.local.family:{plan.session_guid_hex}{t.elem_id:08x}-1.0.0"


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

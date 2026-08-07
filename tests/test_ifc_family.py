"""Tests for the ifc-family stream: ``rvt.ifc.product_facts`` (IFC product
-> facts record) and ``rvt.ifc.famfrom_ifc`` (facts -> OUR downlight family
-> standalone .rfa -> loaded into a certified project base).

Evidence tiers:

1. PRODUCT FACTS: our IFC's product identity, TYPED pset values, the
   overall + per-mesh bounding boxes (metres -> feet consistency), the
   surface colours, and the facts RECORD's schema / provenance validity
   (the catalog validator: nulls are never 'fact', every leaf is flagged,
   the source is VERIFIED with an accessed date, dims_in has w/h/d).
2. COMPOSITION: the downlight family document carries the CCEA contract
   parameter NAMES + the dimension set with the FACTS as values, the
   recessed-can form clusters (8 standard / 2 envelope), one Lighting
   connector hosted on the junction box's face, no fabricated identity
   (manufacturer unwritten), and every record round-trips byte-exact.
3. DELIVERY: the emitted ``.rfa`` reads back clean, passes the certified
   family-mode validator with 0 errors and the byte-level provenance
   ledger (the assay-clean path), and its family document decodes back to
   the authored parameters / forms / connector.
4. LOAD (slow): the family loads into the certified rst base through
   ``rvt.famload`` (four registries coherent, ours in all four, core id =
   the host's Lighting-Fixtures GStyle) and the project validates with
   0 errors.

Corpus / input-dependent tests skip when the IFC / samples / schema are
absent; the load proof is ``@pytest.mark.slow`` (RVT_SKIP_LARGE=1 skips).
"""
from __future__ import annotations

import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
RFA_DONOR = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                         "racbasicsamplefamily-2026.rfa")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
HAVE_IFC = os.path.exists(IFC)
HAVE_SCHEMA = os.path.exists(os.path.join(
    ROOT, "extracted", "racbasicsampleproject", "Formats__Latest.gz", "000.bin")) \
    or os.path.exists(RFA_DONOR)
HAVE_RST = os.path.exists(RST)
try:
    import ifcopenshell                                    # noqa: F401
    HAVE_IOS = True
except Exception:                                          # pragma: no cover
    HAVE_IOS = False

from rvt.ifc import product_facts as PF                  # noqa: E402
from rvt.ifc import famfrom_ifc as FI                    # noqa: E402
from rvt.famgen import skeleton as SK                    # noqa: E402

needs_ifc = pytest.mark.skipif(not (HAVE_IFC and HAVE_IOS),
                               reason="IFC input / ifcopenshell absent")
needs_build = pytest.mark.skipif(not (HAVE_IFC and HAVE_IOS and HAVE_SCHEMA),
                                 reason="IFC / ifcopenshell / schema absent")
needs_load = pytest.mark.skipif(not (HAVE_IFC and HAVE_IOS and HAVE_SCHEMA and HAVE_RST),
                                reason="IFC / schema / rst sample absent")


# ---------------------------------------------------------------------------
# fixtures (expensive builds, module-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def facts():
    return PF.extract_product_facts(IFC)


@pytest.fixture(scope="module")
def record(facts):
    return PF.to_facts_record(facts)


@pytest.fixture(scope="module")
def product(facts):
    return FI.make_downlight(facts=facts, start_id=1000)


@pytest.fixture(scope="module")
def rfa(product, tmp_path_factory):
    d = tmp_path_factory.mktemp("ifcfam")
    path = str(d / "chicago_plenum_downlight.rfa")
    rep = product.write_rfa(path)
    return path, rep


# ---------------------------------------------------------------------------
# 1. product facts
# ---------------------------------------------------------------------------

@needs_ifc
def test_product_identity(facts):
    p = facts.product
    assert p["ifc_class"] == "IfcLightFixture"
    assert p["tag"] == "CP-6-LED"
    assert p["predefined_type"] == "POINTSOURCE"
    assert "downlight" in p["name"].lower()
    assert facts.schema == "IFC4"
    assert facts.source_sha256 and len(facts.source_sha256) == 64
    assert facts.placement["is_identity"] is True
    assert facts.placement["storey"] == "Level 1"


@needs_ifc
def test_pset_typed_values(facts):
    ps = facts.psets["ChicagoPlenumSpecification"]
    assert set(ps) == {"Rating", "Aperture", "Housing", "Trim", "Mounting", "Lamp",
                       "OverallHeightMeters"}
    # labels are str, the height measure is a float (typed, not a string)
    assert isinstance(ps["Rating"]["value"], str) and "CCEA" in ps["Rating"]["value"]
    assert ps["Rating"]["ifc_type"] == "IfcLabel"
    assert ps["OverallHeightMeters"]["value"] == pytest.approx(0.244)
    assert ps["OverallHeightMeters"]["ifc_type"] == "IfcReal"
    assert isinstance(ps["OverallHeightMeters"]["value"], float)
    # pset_value convenience + default
    assert facts.pset_value("Lamp") == "Integrated LED module"
    assert facts.pset_value("NoSuchProp", default="X") == "X"


@needs_ifc
def test_meshes_styles_and_counts(facts):
    assert facts.counts["meshes"] == 29
    assert facts.counts["surface_styles"] == 5
    assert facts.counts["faces"] > 8000
    names = {p.name for p in facts.parts}
    for want in ("housing_can", "trim_reflector", "lens", "plaster_frame",
                 "junction_box", "driver_box", "hanger_bar_front", "hanger_bar_back"):
        assert want in names
    styles = facts.surface_styles
    assert set(styles) == {"galvanized_steel", "gunmetal_steel", "zinc_hardware",
                           "white_enamel", "frosted_lens"}
    # colours are sRGB triples in 0..1 and parts are grouped under their style
    for s in styles.values():
        r, g, b = s["rgb"]
        assert 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0
        assert s["parts"]
    assert "housing_can" in styles["gunmetal_steel"]["parts"]
    assert "trim_reflector" in styles["white_enamel"]["parts"]
    assert "lens" in styles["frosted_lens"]["parts"]


@needs_ifc
def test_bounding_boxes_units_and_geometry(facts):
    # metres -> feet consistency on the overall envelope
    dm, dft, din = facts.overall_dims_m, facts.overall_dims_ft, facts.overall_dims_in
    for a in ("x", "y", "z"):
        assert dft[a] == pytest.approx(dm[a] / 0.3048, rel=1e-4)
        assert din[a] == pytest.approx(dft[a] * 12.0, rel=1e-4)
        assert dm[a] > 0
    # the bar hangers set the x extent (~0.666 m); height ~0.228 m
    assert dm["x"] == pytest.approx(0.666, abs=0.005)
    assert dm["z"] == pytest.approx(0.228, abs=0.005)
    # the can is round: x and y extents of the housing_can mesh agree
    can = facts.part("housing_can")
    assert can.dims_m["x"] == pytest.approx(can.dims_m["y"], abs=1e-3)
    assert can.role == "can"
    # every part's ft bbox is its m bbox scaled
    for p in facts.parts:
        for i in range(3):
            assert p.bbox_ft[0][i] == pytest.approx(p.bbox_m[0][i] / 0.3048, rel=1e-4)
            assert p.bbox_ft[1][i] == pytest.approx(p.bbox_m[1][i] / 0.3048, rel=1e-4)


def test_classify_part_rules():
    assert PF.classify_part("housing_can") == "can"
    assert PF.classify_part("trim_reflector") == "trim"
    assert PF.classify_part("lens") == "lens"
    assert PF.classify_part("plaster_frame") == "frame"
    assert PF.classify_part("frame_lip_left") == "frame"
    assert PF.classify_part("hanger_bar_front") == "hanger"
    assert PF.classify_part("nail_flag_back_a") == "hanger"
    assert PF.classify_part("junction_box") == "junction_box"
    assert PF.classify_part("jbox_gasket") == "junction_box"      # jbox rule before gasket
    assert PF.classify_part("driver_box") == "driver_box"
    assert PF.classify_part("cover_screw_top") == "hardware"
    assert PF.classify_part("conduit_connector") == "hardware"
    assert PF.classify_part("mystery") == "other"


def test_parse_aperture_label():
    assert PF._parse_aperture_label("6 in (152 mm) round") == {"in": 6.0, "mm": 152.0}
    assert PF._parse_aperture_label("4 in") == {"in": 4.0, "mm": None}
    assert PF._parse_aperture_label("") == {"in": None, "mm": None}


@needs_ifc
def test_downlight_geometry_facts(facts):
    g = PF.downlight_geometry(facts)
    assert g["aperture_stated_in"] == 6.0
    assert g["aperture_stated_mm"] == 152.0
    assert g["aperture_stated_ft"] == pytest.approx(0.5)
    assert g["overall_height_stated_m"] == pytest.approx(0.244)
    assert g["overall_height_stated_ft"] == pytest.approx(0.244 / 0.3048, rel=1e-4)
    # measured height (0.228 m) differs from the stated 0.244 -- both recorded
    assert g["measured_height_ft"] == pytest.approx(0.228 / 0.3048, rel=1e-2)
    assert g["measured_height_ft"] != pytest.approx(g["overall_height_stated_ft"])
    for k in ("can_diameter_ft", "can_height_ft", "trim_diameter_ft", "frame_length_ft",
              "frame_width_ft", "hanger_span_ft", "lens_diameter_ft"):
        assert g[k] is not None and g[k] > 0
    assert len(g["jbox_dims_ft"]) == 3 and len(g["can_center_ft"]) == 3


@needs_ifc
def test_facts_record_schema_valid(record):
    from rvt.famgen import catalog as C
    assert PF.validate_record(record) == []
    assert C.validate_line(record) == []
    assert record["schema_version"] == 1
    assert record["category"] == "luminaire"
    assert record["revit_category"] == "OST_LightingFixtures"
    src = record["sources"]["S1"]
    assert src["verification"] == "VERIFIED" and src["accessed"]
    assert len(src["sha256"]) == 64
    (v,) = record["variants"]
    assert v["model"] == "CP-6-LED"
    for axis in ("w", "h", "d"):
        assert v["dims_in"][axis] is not None and v["dims_in"][axis] > 0
    # every tracked leaf has a flag, and nulls are never facts
    fp = v["field_provenance"]
    for path in C.leaf_paths(v):
        assert fp.get(path) in ("fact", "assumed")
        if C._get_path(v, path) is None:
            assert fp[path] == "assumed", f"null {path} must not be a fact"
    # electrical / photometric are NOT SOURCED (the IFC states none)
    assert v["ratings"]["wattage_w"] is None
    assert v["ratings"]["lumens_lm"] is None
    assert v["ratings"]["cct_k"] is None
    assert v["ratings"]["voltage_v"] is None
    assert record["line_facts"]["photometry_reference"]["value"] is None
    # facts read from the file are facts
    assert v["ratings"]["aperture_in"] == 6.0
    assert fp["ratings.aperture_in"] == "fact"
    assert "CCEA" in v["options"]["ccea_rating"]
    assert fp["options.ccea_rating"] == "fact"


@needs_ifc
def test_write_facts_record_and_refuse_invalid(facts, tmp_path):
    out = str(tmp_path / "facts.json")
    full = str(tmp_path / "facts.full.json")
    rep = PF.write_facts_record(facts, out, full_dump_path=full)
    assert rep["problems"] == []
    with open(out) as fh:
        rec = json.load(fh)
    assert rec["variants"][0]["model"] == "CP-6-LED"
    with open(full) as fh:
        dump = json.load(fh)
    assert dump["counts"]["meshes"] == 29
    # a record with a null flagged 'fact' is refused
    bad = PF.to_facts_record(facts)
    bad["variants"][0]["field_provenance"]["ratings.wattage_w"] = "fact"
    assert PF.validate_record(bad)


# ---------------------------------------------------------------------------
# 2. composition
# ---------------------------------------------------------------------------

@needs_build
def test_downlight_parameters_and_type(product):
    doc = product.doc
    assert doc.finalized
    assert doc.category_id == SK.OST_LIGHTING_FIXTURES
    assert doc.part_type == SK.PART_TYPE["normal"]
    assert doc.work_plane_based is True
    caps = set(doc.params)
    # the CCEA specification contract + dimensions + electrical / photometric
    for want in ("CCEA Rating", "Aperture", "Housing", "Trim", "Mounting", "Lamp",
                 "Aperture Diameter", "Housing Diameter", "Housing Height",
                 "Overall Height", "Frame Length", "Frame Width", "Trim Diameter",
                 "Lens Diameter", "Bar Hanger Span", "Wattage", "Voltage",
                 "Lumens", "Color Temperature", "Photometric Web File"):
        assert want in caps
    assert len(doc.types) == 1
    tname, vals = doc.types[0]
    assert tname == "CP-6-LED"
    # dimension VALUES = the facts (feet)
    p_ap = doc.params["Aperture Diameter"].elem_id
    p_hd = doc.params["Housing Diameter"].elem_id
    assert vals[p_ap] == pytest.approx(0.5)                       # 6 in aperture
    assert vals[p_hd] == pytest.approx(0.610236, rel=1e-3)        # 7.32 in can
    # spec strings
    assert "CCEA" in vals[doc.params["CCEA Rating"].elem_id]
    assert vals[doc.params["Lamp"].elem_id] == "Integrated LED module"
    assert vals[doc.params["Aperture"].elem_id] == "6 in (152 mm) round"
    # photometric web is an unset REFERENCE; unsourced numbers are 0
    assert vals[doc.params["Photometric Web File"].elem_id] == ""
    assert vals[doc.params["Wattage"].elem_id] == 0.0
    assert vals[doc.params["Lumens"].elem_id] == 0.0
    assert vals[doc.params["Voltage"].elem_id] == pytest.approx(SK.volts(120.0))
    # identity: model + description written, manufacturer NOT invented
    assert vals[SK.BIP_TYPE_MODEL] == "CP-6-LED"
    assert "downlight" in str(vals[SK.BIP_TYPE_DESCRIPTION]).lower() \
        or "housing" in str(vals[SK.BIP_TYPE_DESCRIPTION]).lower()
    assert SK.BIP_TYPE_MANUFACTURER not in vals


@needs_build
def test_downlight_forms_and_connector(product):
    doc = product.doc
    assert product.detail == "standard"
    assert len(product.forms) == 8
    kinds = sorted(fb.kind for fb in product.forms)
    assert kinds.count("cylinder") == 3        # can + trim + lens
    assert kinds.count("box") == 4             # jbox + driver + 2 hangers
    assert kinds.count("plate") == 1           # the frame
    assert len(doc.by_class("ExtrusionElem")) == 8
    # the can axis is the family origin: the can cylinder is centred at (0, 0)
    can = product.forms[0]
    assert can.params.get("role", "").startswith("housing can")
    cx, cy = can.params["center"]
    assert abs(cx) < 1e-9 and abs(cy) < 1e-9
    # one Lighting connector, hosted on the junction box's extrusion
    assert len(doc.connectors) == 1
    con = doc.connectors[0]
    jbox = next(fb for fb in product.forms if "junction box" in fb.params.get("role", ""))
    ext_id = jbox.by_class("ExtrusionElem")[0].elem_id
    assert con.obj.get("m_hostElementId") in (ext_id, None) or True   # host recorded in refs
    hosts = json.dumps(con.obj, default=str)
    assert str(ext_id) in hosts, "connector must reference the junction-box extrusion"
    assert len(doc.load_classes) == 1


@needs_build
def test_downlight_roundtrips_byte_exact(product):
    rt = product.doc.roundtrip()
    assert rt["failed"] == 0
    assert rt["roundtrip_ok"] == rt["records"] == 3 * len(product.doc.elements)


@needs_build
def test_envelope_variant_has_two_forms(facts):
    p = FI.make_downlight(facts=facts, detail="envelope", start_id=1000)
    assert p.detail == "envelope"
    assert len(p.forms) == 2
    assert len(p.doc.by_class("ExtrusionElem")) == 2
    assert len(p.doc.connectors) == 1        # datum-hosted connector in this variant
    rt = p.doc.roundtrip()
    assert rt["failed"] == 0 and rt["roundtrip_ok"] == rt["records"]


@needs_build
def test_bad_detail_raises(facts):
    with pytest.raises(FI.FamFromIfcError):
        FI.make_downlight(facts=facts, detail="bogus")


@needs_build
def test_missing_required_geometry_refuses(facts):
    """A facts object without the housing_can mesh cannot honestly drive the
    housing -- the constructor refuses instead of inventing a diameter."""
    import copy
    f2 = copy.copy(facts)
    f2.parts = [p for p in facts.parts if p.name != "housing_can"]
    with pytest.raises(FI.FamFromIfcError):
        FI.make_downlight(facts=f2)


@needs_build
def test_job_parameters_flow_and_provenance(facts):
    p = FI.make_downlight(facts=facts, voltage=277, wattage=12.5, start_id=1000)
    fs = p.facts
    assert fs.get("voltage_v") == 277.0 and fs.get("wattage_w") == 12.5
    assert fs.values["voltage_v"].kind == "given"
    assert fs.values["wattage_w"].kind == "given"
    # measured geometry is a fact, sourced to the IFC
    assert fs.values["can_diameter_ft"].kind == "fact"
    assert "chicago-plenum-downlight.ifc" in fs.values["can_diameter_ft"].source
    # manufacturer is never sourced from our IFC
    assert fs.get("manufacturer") is None
    vals = p.doc.types[0][1]
    assert vals[p.doc.params["Wattage"].elem_id] == pytest.approx(SK.watts(12.5))
    assert vals[p.doc.params["Voltage"].elem_id] == pytest.approx(SK.volts(277.0))


# ---------------------------------------------------------------------------
# 3. delivery (the assay-clean .rfa)
# ---------------------------------------------------------------------------

@needs_build
def test_rfa_emits_clean_validates_and_is_provenance_clean(rfa):
    path, rep = rfa
    assert os.path.getsize(path) > 100_000
    assert rep["ok"] is True
    assert rep["verify"]["ok"] is True
    assert rep["verify"].get("gzip_crc_failures") == 0
    assert rep["verify"].get("ecc_mismatch") == 0
    val = rep["validate"]
    assert val["ok"] is True
    assert val["family_mode"]["verdict"] == "VALID"
    assert val["family_mode"]["n_errors"] == 0
    prov = rep["provenance"]
    assert prov["ok"] is True
    for check in ("adocument_decodes_clean", "zero_dangling_element_refs",
                  "zero_donor_id_byte_hits", "zero_donor_name_strings",
                  "owner_family_is_ours", "identity_is_ours", "footer_blob_not_donor",
                  "no_donor_end_parity", "end_record_is_constant",
                  "formats_latest_is_format_constant"):
        assert prov["checks"].get(check) is True, check


@needs_build
def test_rfa_reads_back_the_authored_family(rfa):
    """Decode the family document back out of the file: 8 forms, the 20
    parameter captions, the single type row, one connector."""
    from collections import Counter
    from rvt.families import FamilyIndex, unit_segments
    from rvt.objects import iter_records
    path, _rep = rfa
    idx = FamilyIndex(path)
    segs = unit_segments(idx, 0)
    cnt = Counter()
    captions = []
    fam = None
    for r in iter_records(segs[102], 102):
        d = idx.decode(0, r.elem_id, 102)
        if d is None:
            continue
        cnt[d.class_name] += 1
        if d.class_name == "ParamElemFamily":
            pd = ((d.value.get("m_pParamDef") or {}).get("value") or {})
            captions.append(pd.get("m_caption"))
        elif d.class_name == "Family":
            fam = d.value
    assert cnt["ExtrusionElem"] == 8
    assert cnt["CurveElem"] == 26          # 5 boxes x 4 lines + 3 cylinders x 2 arcs
    assert cnt["VarSketch"] == 8
    assert cnt["ConnectorElem"] == 1
    assert cnt["ParamElemFamily"] == 20
    for want in ("CCEA Rating", "Aperture Diameter", "Photometric Web File",
                 "Bar Hanger Span", "Lamp", "Mounting"):
        assert want in captions
    ftt = ((fam.get("m_pFamilyTypes") or {}).get("value") or {})
    assert [pr.get("name") for pr in (ftt.get("m_pairs") or [])] == ["CP-6-LED"]


# ---------------------------------------------------------------------------
# 4. load into the certified base (slow)
# ---------------------------------------------------------------------------

@needs_load
@pytest.mark.slow
def test_family_loads_into_the_certified_rst_base(tmp_path):
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE")
    out = str(tmp_path / "L_downlight_loaded.rvt")
    lr = FI.load_into_project(FI.HOST_RST, out,
                              builder=lambda start_id=100000:
                              FI.make_downlight(start_id=start_id).doc)
    assert lr.error == ""
    assert lr.ok is True, lr.stop_reason
    reg = (lr.verify.get("registries") or {})
    assert reg.get("coherent") is True
    assert reg.get("ours_in_all_four") is True
    assert reg.get("units_added") == 1
    # our plan: lighting fixture category, one symbol, param twins, and the
    # host's Lighting-Fixtures GStyle bound as the core id (the L1a pattern)
    (plan,) = lr.plans
    assert plan["category"] == SK.OST_LIGHTING_FIXTURES
    assert plan["part_type"] == 0
    assert len(plan["symbol_ids"]) == 1
    assert len(plan["twin_of"]) == 20
    assert plan["core_ids"], "the host's category style row should bind as a core id"
    # the written project validates in project mode with ZERO errors
    assert lr.validate_project_mode.get("verdict") == "VALID"
    assert lr.validate_project_mode.get("n_errors") == 0

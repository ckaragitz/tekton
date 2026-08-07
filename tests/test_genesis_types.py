"""Tests for rvt.genesis.types: system-family-type + document-standard
constructors built from PLAIN PARAMETERS (no cloned Autodesk payload).

Three tiers:
  1. schema-only (fast): every product of ``blank_object`` and every
     constructor encodes with rvt.encode and decodes back CLEAN and
     BYTE-EXACT with an equal value tree;
  2. structural rules: the compound-structure vertical-region grid, shell
     counts, reference-face keys, unit factors;
  3. PARAMETRIC REPRODUCTION (needs the rme corpus): re-create Autodesk's
     own types from their plain parameters and prove the object AND header
     are field-for-field identical (the strongest correctness evidence a
     constructor can have without a viewer test).

Set ``RVT_SEG_CACHE`` to reuse the concatenated segments between runs.
"""
import json
import os

import pytest

from rvt.genesis import types as G

CACHE = os.environ.get("RVT_SEG_CACHE")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_CLASSES = [
    "BasicWallType", "FloorAttributes", "CompoundCeilingType", "RoofAttributes",
    "RbsConduitType", "ConduitStandardType", "RbsCableTrayType", "RbsWireType",
    "RbsWireMaterialType", "RbsWireInsulationType", "RbsWireTemperatureRatingType",
    "RbsVoltageType", "RbsDistributionSysType", "ElectricalLoadClassification",
    "ElectricalDemandFactorDefinition", "MaterialElem", "LinePatternElem",
    "FillPatternElem", "TextNoteAttributes", "FontElem", "DimensionStyle",
    "CategoryElem", "GStyleElem", "CustomElement", "ConduitSizesElem",
    "CableTraySizesElem", "ElectricalSetting", "RbsWireSizesElem",
    "ElementHeader", "GElement", "Geometry",
]


# ---------------------------------------------------------------------------
# tier 1: schema-driven skeleton + constructors round-trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", TARGET_CLASSES)
def test_blank_object_roundtrips(cls):
    dec, enc, schema = G._S()
    cid = schema.by_name[cls].type_id
    obj = G.blank_object(cls)
    body = enc.encode_object(cid, obj)
    got = dec.decode_record(cid, body)
    assert got.clean, got.errors
    assert enc.encode_object(cid, got.value) == body
    assert G._values_equal(got.value, obj)


def test_element_header_shape():
    h = G.element_header("BasicWallType", G.OST_Walls, 500001,
                         deletion_ids=[500002, 3])
    assert h["m_categroryId"] == -2000011
    assert h["m_classDef"] == {"m_ref": {"classref": "BasicWallType"}}
    assert h["m_parents"]["value"]["m_deletion"] == [3, 500001, 500002]
    assert h["m_abFlags4Bytes"] == 2364            # verified rme constant
    dec, enc, schema = G._S()
    cid = schema.by_name["ElementHeader"].type_id
    body = enc.encode_object(cid, h)
    assert dec.decode_record(cid, body).clean


def _roundtrip_ok(rec):
    rep = rec.roundtrip()
    for seq in (101, 102, 103):
        assert rep[seq]["clean"], (rec.class_name, seq, rep[seq]["errors"])
        assert rep[seq]["byte_exact"], (rec.class_name, seq)
        assert rep[seq]["value_equal"], (rec.class_name, seq)
    assert rep["ok"]
    return rep


def test_constructors_roundtrip_all():
    ids = G.IdSource(700_000)
    recs = []
    recs.append(G.new_wall_type("W1", [("finish2", 16, -1), ("structure", 92, -1),
                                       ("finish1", 16, -1)], ids=ids))
    recs.append(G.new_floor_type("F1", [("structure", 150, -1)], ids=ids))
    recs.append(G.new_roof_type("R1", [("structure", 300, -1)], ids=ids))
    recs.append(G.new_ceiling_type("C1", [("finish2", 16, -1), ("structure", 30, -1)],
                                   ids=ids))
    recs.append(G.new_material("M1", (10, 20, 30), ids=ids))
    recs.append(G.new_line_pattern("Dash", [("dash", 3), ("space", 3)], ids=ids))
    recs.append(G.new_fill_pattern("Cross", [{"angle_deg": 45, "spacing_mm": 3},
                                             {"angle_deg": 135, "spacing_mm": 3}], ids=ids))
    recs.append(G.new_fill_pattern("Solid", [], ids=ids))
    recs.append(G.new_voltage_type("208", 208, ids=ids))
    recs.append(G.new_distribution_system("120/208 Wye", phase="three", config="wye",
                                          wires=4, ids=ids))
    recs.append(G.new_conduit_standard("EMT", ids=ids))
    recs.append(G.conduit_sizes_element({700100: [(0.5, 0.622, 0.706, 4.35)]}, ids=ids))
    recs.append(G.new_conduit_type("EMT Conduit", standard_id=700100,
                                   with_fitting=True, ids=ids))
    recs.append(G.cable_tray_sizes_element([4, 6, 8], ids=ids))
    recs.append(G.new_cable_tray_type("Ladder", shape="ladder", ids=ids))
    recs.append(G.new_cable_tray_type("Solid", shape="ushape", ids=ids))
    recs.append(G.new_conductor_material("Copper", ids=ids))
    recs.append(G.new_conductor_temperature_rating("75", ids=ids))
    recs.append(G.new_conductor_insulation("THWN", ids=ids))
    recs.append(G.new_conductor_size("500", 21.79, ids=ids))
    recs.append(G.new_wire_type("THWN", material_id=1, temperature_rating_id=2,
                                insulation_id=3, max_size_id=4, ids=ids))
    recs.append(G.new_wire_material_type("Copper", ids=ids))
    recs.append(G.new_wire_insulation_type("THWN", ids=ids))
    recs.append(G.new_wire_temperature_rating_type("75", ids=ids))
    recs.append(G.new_demand_factor("DF const", 1.0, ids=ids))
    recs.append(G.new_demand_factor("DF stepped", 1.0, ids=ids, rule="load",
                                    rows=[(0, 1e4, 1.0), (1e4, 1e30, 0.5)]))
    recs.append(G.new_load_class("Lighting", 700200, ids=ids))
    recs.append(G.electrical_setting(ids=ids))
    recs.extend(G.new_text_type("3.2mm Arial", ids=ids))
    recs.append(G.new_category("Sub", -2008130, gstyle_ids=[7], ids=ids))
    recs.append(G.new_gstyle(-2000011, style_type="cut", pen=3, ids=ids))
    recs.append(G.new_gstyle(700300, style_type="projection", pen=1, ids=ids))
    for r in recs:
        _roundtrip_ok(r)
    # (class_id, obj_dict, header_dict) contract
    cid, obj, hdr = recs[0].as_tuple()
    assert cid == G.class_id("BasicWallType")
    assert obj["m_symbolInfo"]["value"]["m_name"] == "W1"
    assert hdr["m_categroryId"] == G.OST_Walls


def test_default_object_styles_from_table():
    ids = G.IdSource(710_000)
    styles = G.default_object_styles(ids, categories=[G.OST_Walls, G.OST_Conduit,
                                                       G.OST_CableTray])
    assert len(styles) >= 3
    for s in styles:
        _roundtrip_ok(s)
        assert s.obj["m_categoryId"] < 0                 # built-in category rows
        assert s.header["m_abFlags4Bytes"] == 67108894  # object-style header flags
    tab = G.object_styles_table()
    assert tab["categories"] >= 900
    assert tab["entries_confirmed_constant"] > 1000
    conduit = tab["styles"][str(G.OST_Conduit)]["projection"]
    assert conduit["pen"] == 1 and conduit["pattern_id"] == G.LINEPATTERN_SOLID


def test_demo_catalog_is_clean():
    cat = G.demo_catalog(start=720_000)
    rt = cat.roundtrip()
    assert rt["records"] >= 50
    assert rt["ok"] == rt["records"], rt["failures"][:2]
    assert cat.check_references() == []
    # every record adapts to a mutate.NewElement with 3 records
    els = cat.new_elements()
    assert len(els) == rt["records"]
    assert all(len(el.records()) == 3 for el in els)


# ---------------------------------------------------------------------------
# tier 2: structural rules + units
# ---------------------------------------------------------------------------

def test_unit_factors():
    assert abs(G.volts(240) - 2583.3385) < 0.01           # rme RbsVoltageType '240'
    assert abs(G.volts(208) - 2238.89) < 0.05            # KNOWLEDGE.md circuit value
    assert abs(G.mm(304.8) - 1.0) < 1e-12
    assert abs(G.inches(6) - 0.5) < 1e-12
    assert G.rgb(0xFB, 0xC5, 0x99) == 10077691             # rme material colorref


def test_wall_grid_single_layer_matches_revit_rule():
    # 'MW 17.5' = one 175 mm layer: 2 boundary segments + 2 faces, one region,
    # ref-face keys 29 (core exterior) and 30 (core interior)
    norm = G._norm_layers([("structure", 175.0, -1)])
    vr = G._vertical_regions(norm, 20.0)["structure"]["value"]
    g = vr["m_grid"]
    assert [s["m_id"] for s in g["m_segments"]] == [2, 3, 0, 1]      # faces then bounds
    assert [round(s["m_coordinate"], 6) for s in g["m_segments"][2:]] == \
        [0.0, round(175.0 / 304.8, 6)]
    assert g["m_regions"] == [{"m_id": 0, "m_segmentIds": [0, 2, 1, 3]}]
    assert vr["m_regionToLayerMap"] == [{"first": 0, "second": 0}]
    assert G._seg_ref_face_keys(norm) == [{"m_id": 0, "m_key0": 29, "m_key1": 0},
                                           {"m_id": 1, "m_key0": 30, "m_key1": 0}]
    assert G._shell_counts(norm) == (0, 0, 0)


def test_wall_grid_seven_layer_block_wall_rule():
    # 'Exterior - Block on Mtl. Stud': 7 layers, two ZERO-width membranes get
    # no region; shells 4 ext / 2 int; core = layer 4; keys 31,31,29,30
    layers = [(4, 200.0, -1), (3, 76.0, -1), (100, 0.0, -1), (2, 19.0, -1),
              (1, 152.0, -1), (100, 0.0, -1), (5, 13.0, -1)]
    norm = G._norm_layers(layers)
    vr = G._vertical_regions(norm, 19.685)["structure"]["value"]
    g = vr["m_grid"]
    assert len(g["m_regions"]) == 5                                  # membranes dropped
    assert vr["m_regionToLayerMap"] == [
        {"first": 0, "second": 0}, {"first": 1, "second": 1}, {"first": 2, "second": 3},
        {"first": 3, "second": 4}, {"first": 4, "second": 6}]
    assert G._shell_counts(norm) == (4, 2, 4)
    keys = G._seg_ref_face_keys(norm)
    assert keys == [{"m_id": 1, "m_key0": 31, "m_key1": 0},
                    {"m_id": 2, "m_key0": 31, "m_key1": 1},
                    {"m_id": 3, "m_key0": 29, "m_key1": 0},
                    {"m_id": 4, "m_key0": 30, "m_key1": 0}]
    # bottom faces, top faces, then boundaries; face ids B+2r / B+2r+1
    ids = [s["m_id"] for s in g["m_segments"]]
    assert ids == [6, 8, 10, 12, 14, 7, 9, 11, 13, 15, 0, 1, 2, 3, 4, 5]


def test_wall_type_definition_fields():
    rec = G.new_wall_type("Party Wall", [("finish2", 16, 601), ("structure", 92, 602),
                                        ("finish1", 16, 601)], elem_id=600001)
    cs = rec.obj["m_pCompoundStructure"]["value"]
    ws = [L["m_layerWidth"] for L in cs["m_layers"]]
    assert abs(sum(ws) * 304.8 - 124.0) < 1e-6
    assert [L["m_layerFunction"] for L in cs["m_layers"]] == [5, 1, 4]
    assert [L["m_materialId"] for L in cs["m_layers"]] == [601, 602, 601]
    assert cs["m_numShellLayersExt"] == 1 and cs["m_numShellLayersInt"] == 1
    assert cs["m_structuralMaterialLayerIndex"] == 1
    assert rec.obj["m_symbolInfo"]["value"]["m_name"] == "Party Wall"
    assert rec.rep is not None                                        # empty GElement rep
    assert set(rec.header["m_parents"]["value"]["m_deletion"]) >= {600001, 601, 602}
    _roundtrip_ok(rec)


def test_voltage_ranges_and_distribution_encoding():
    v = G.new_voltage_type("240", 240, elem_id=1)
    assert abs(v.obj["m_dMinVoltage"] - G.volts(220)) < 1e-6
    assert abs(v.obj["m_dMaxVoltage"] - G.volts(250)) < 1e-6
    d = G.new_distribution_system("480/277 Wye", phase="three", config="wye", wires=4,
                                  voltage_ll_id=10, voltage_lg_id=11, elem_id=2)
    assert (d.obj["m_kPhase"], d.obj["m_kConfig"], d.obj["m_iNumWires"]) == (1, 1, 4)
    assert (d.obj["m_idVll"], d.obj["m_idVlg"]) == (10, 11)
    single = G.new_distribution_system("120/240", phase="single", config="delta",
                                       wires=3, elem_id=3)
    assert (single.obj["m_kPhase"], single.obj["m_kConfig"]) == (0, 0)


def test_no_cloned_payload_source():
    # the constructors module must not read any .rvt / corpus file
    src = open(os.path.join(ROOT, "src/rvt/genesis/types.py")).read()
    for banned in ("Document.load", "from_file(", "open_rvt", "samples/", "extracted/"):
        assert banned not in src, banned


# ---------------------------------------------------------------------------
# tier 3: PARAMETRIC REPRODUCTION of Autodesk's own types (rme corpus)
# ---------------------------------------------------------------------------

_have_corpus = os.path.isdir(os.path.join(ROOT, "extracted", "rmebasicsampleproject"))


@pytest.fixture(scope="module")
def rme():
    if not _have_corpus:
        pytest.skip("rme corpus not extracted")
    from rvt.mutate import Document
    return Document.load("rmebasicsampleproject", CACHE)


def _diff(a, b, path="", out=None):
    out = [] if out is None else out
    norm = lambda v: round(v, 6) if isinstance(v, float) else v   # noqa: E731
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            if k not in a or k not in b:
                out.append((path + "." + k, k in a, k in b))
            else:
                _diff(a[k], b[k], path + "." + k, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            _diff(x, y, f"{path}[{i}]", out)
    elif norm(a) != norm(b):
        out.append((path, a, b))
    return out


def test_reproduce_voltage_and_distribution(rme):
    # RbsVoltageType '240' (id 277806) and the 120/240 single system (277809)
    rec = G.new_voltage_type("240", 240, min_volts=220, max_volts=250, elem_id=277806)
    assert _diff(rec.obj, rme.value(277806)) == []
    assert _diff(rec.header, rme.decode(277806, 101).value) == []
    d = G.new_distribution_system("120/240 Single", phase="single", config="delta",
                                  wires=3, voltage_ll_id=277806, voltage_lg_id=55359,
                                  elem_id=277809)
    assert _diff(d.obj, rme.value(277809)) == []
    assert _diff(d.header, rme.decode(277809, 101).value) == []


def test_reproduce_wire_conduit_cabletray(rme):
    # conductor cells + wire type XHHW (261496): object AND header exact
    assert _diff(G.new_conductor_material("Copper", elem_id=887961).obj,
                 rme.value(887961)) == []
    assert _diff(G.new_conductor_temperature_rating("60", elem_id=887962).obj,
                 rme.value(887962)) == []
    assert _diff(G.new_conductor_insulation("XHHW", elem_id=887992).obj,
                 rme.value(887992)) == []
    assert _diff(G.new_conductor_size("2000", 0.117851167 * 304.8, elem_id=887990).obj,
                 rme.value(887990)) == []
    wt = G.new_wire_type("XHHW", material_id=887961, temperature_rating_id=887962,
                         insulation_id=887992, max_size_id=887990, elem_id=261496)
    assert _diff(wt.obj, rme.value(261496)) == []
    assert _diff(wt.header, rme.decode(261496, 101).value) == []
    # conduit type RNC Sch 80 (662478) from its plain parameters
    r = rme.value(662478)
    fit = {"cross": r["m_idDefaultCross"], "elbow": r["m_idDefaultElbow"],
           "tee": r["m_idDefaultTee"], "transition": r["m_idDefaultTransition"],
           "union": r["m_idDefaultUnion"]}
    ct = G.new_conduit_type(r["m_symbolInfo"]["value"]["m_name"],
                            standard_id=r["m_idStandardType"],
                            with_fitting=r["m_bWithFitting"], fittings=fit,
                            preview_id=r["m_previewElemId"], elem_id=662478)
    assert _diff(ct.obj, r) == []
    assert _diff(ct.header, rme.decode(662478, 101).value) == []
    # cable tray type (643892)
    r = rme.value(643892)
    fit = {"cross": r["m_idDefaultCross"], "elbow": r["m_idDefaultElbow"],
           "elbow_up": r["m_idDefaultElbowUp"], "elbow_down": r["m_idDefaultElbowDown"],
           "tee": r["m_idDefaultTee"], "transition": r["m_idDefaultTransition"],
           "union": r["m_idDefaultUnion"]}
    ct = G.new_cable_tray_type(r["m_symbolInfo"]["value"]["m_name"],
                               shape=("ladder" if r["m_eCableTrayType"] == 2 else "ushape"),
                               with_fitting=r["m_bWithFitting"], fittings=fit,
                               preview_id=r["m_previewElemId"], elem_id=643892)
    assert _diff(ct.obj, r) == []


def test_reproduce_conduit_sizes_and_electrical_setting(rme):
    v = rme.value(638845)                     # the ConduitSizesElem singleton
    sz = {}
    for p in v["m_sizes"]:
        sz[p["first"]] = [{"nominal_in": r["m_dSize"] * 12,
                            "inner_in": r["m_dInnerDiameter"] * 12,
                            "outer_in": r["m_dOuterDiameter"] * 12,
                            "bend_radius_in": r["m_dBendRadius"] * 12,
                            "in_size_list": r["m_bInSizeList"],
                            "used_by_sizing": r["m_bUsedBySizing"]}
                           for r in p["second"]["m_sizeData"]]
    assert _diff(G.conduit_sizes_element(sz, elem_id=638845).obj, v) == []
    v = rme.value(639116)                     # the ElectricalSetting singleton
    rec = G.electrical_setting(
        elem_id=639116,
        phase_labels=(v["m_circuitNamePhaseA"], v["m_circuitNamePhaseB"],
                      v["m_circuitNamePhaseC"]),
        circuit_rating=v["m_circuitRating"],
        circuit_path_offset_mm=v["m_circuitPathOffset"] * 304.8,
        specific_angles_deg=[a["first"] for a in v["m_specificAngles"]],
        load_calc_method=v["m_circuitLoadCalculationMethod"],
        run_load_calcs_in_spaces=v["m_isRunCalculationsForLoadsInSpaces"],
        include_spares_in_totals=v["m_isIncludeSparesInPanelTotals"],
        merge_multi_pole_circuits=v["m_mergeMultiPoledCircuitsIntoSingleCell"])
    assert _diff(rec.obj, v) == []


def test_reproduce_wall_and_flat_types(rme):
    def layers(vv):
        cs = vv["m_pCompoundStructure"]["value"]
        return [{"function": L["m_layerFunction"], "thickness_ft": L["m_layerWidth"],
                 "material_id": L["m_materialId"]} for L in cs["m_layers"]], cs
    # the US 7-layer block wall (54538): compound structure + grid + rep exact
    v = rme.value(54538)
    lay, cs = layers(v)
    vr = cs["m_oVertRegStructure"]["value"]
    rec = G.new_wall_type("Exterior - Block on Mtl. Stud", lay, family_name=None,
                          function=v["m_function"],
                          sample_height_mm=vr["m_sampleHeight"] * 304.8,
                          fill_pattern_id=cs["m_coarseScaleFillPatternElemId"],
                          preview_id=v["m_previewElemId"],
                          default_height_constraint=3, elem_id=54538)
    d = _diff(rec.obj, v)
    # only the pre-Revit-4.0 legacy key list (m_segRefFaceKeysPre40) differs
    assert [p for p, _a, _b in d] == [".m_pCompoundStructure.value.m_segRefFaceKeysPre40"]
    assert _diff(rec.header, rme.decode(54538, 101).value) == []
    assert _diff(rec.rep, rme.decode(54538, 103).value) == []       # empty GElement rep
    # roof 'Generic - 400mm' (335): EXACT
    v = rme.value(335)
    lay, cs = layers(v)
    r = G.new_roof_type("Generic - 400mm", lay, preview_id=v["m_previewElemId"],
                        elem_id=335)
    assert _diff(r.obj, v) == []
    assert _diff(r.header, rme.decode(335, 101).value) == []
    # compound ceiling (563403): EXACT
    v = rme.value(563403)
    lay, cs = layers(v)
    c = G.new_ceiling_type(v["m_symbolInfo"]["value"]["m_name"], lay,
                           preview_id=v["m_previewElemId"], elem_id=563403,
                           system_name=v["m_system"])
    assert _diff(c.obj, v) == []


def test_reproduce_patterns_text_and_object_styles(rme):
    # line pattern 'Dash' (11) and 'Dot' (18)
    assert _diff(G.new_line_pattern("Dash", [("dash", 3.175), ("space", 3.175)],
                                    elem_id=11).obj, rme.value(11)) == []
    assert _diff(G.new_line_pattern("Dot", [("dot", 0.0), ("space", 4.7625)],
                                    elem_id=18).obj, rme.value(18)) == []
    # fill pattern 'Diagonal crosshatch' (6473)
    sp = 0.009836066 * 304.8
    fp = G.new_fill_pattern("Diagonal crosshatch",
                            [{"angle_deg": 45, "spacing_mm": sp},
                             {"angle_deg": 135, "spacing_mm": sp}],
                            window_size_mm=0.008145492 * 304.8, elem_id=6473)
    assert _diff(fp.obj, rme.value(6473)) == []
    # a real text type + its owned font/category/gstyle (618030..618033)
    recs = G.new_text_type('1/8" Arial', font="Arial",
                           size_mm=0.010416666666666668 * 304.8,
                           tab_size_mm=0.041666667 * 304.8,
                           leader_offset_mm=0.006666667 * 304.8,
                           leader_arrowhead_id=583374,
                           elem_ids=[618030, 618033, 618031, 618032],
                           color=16777216)
    for rec, real in zip(recs, (618030, 618033, 618031, 618032)):
        assert _diff(rec.obj, rme.value(real)) == [], (rec.class_name, real)
        assert _diff(rec.header, rme.decode(real, 101).value) == [], (rec.class_name, real)
    # the OST_Walls object-style rows (ids 30 = projection pen 1, 31 = cut pen 3)
    assert _diff(G.new_gstyle(-2000011, style_type="projection", pen=1, color=0,
                              line_pattern_id=-3000010, material_id=24, elem_id=30).obj,
                 rme.value(30)) == []
    assert _diff(G.new_gstyle(-2000011, style_type="cut", pen=3, color=0,
                              line_pattern_id=-3000010, material_id=24, elem_id=31).obj,
                 rme.value(31)) == []

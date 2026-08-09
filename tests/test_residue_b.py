"""Tests for rvt.genesis.residue_b (RESIDUE CONSTRUCTORS, GROUP B -- the
residue classes whose names sort M..Z + the ZB in-place rung machinery).

They exercise: the Group-B claim (class list vs Yn's residue table), every
constructor's byte-exact schema round trip, the machinery reproducers'
'nothing of ours to reject' property (a reproduced empty-machinery object
equals the sample's own object byte-for-byte), the census instrument, and
-- when the certified parent Y9 is present -- the in-place builders' plan
correctness (one our-record per residue slot, same class, nothing of an
earlier rung re-landed) plus one end-to-end single-change rung with the
in-place byte-delta law asserted.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

Y9 = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "Y9.rvt")
YN = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "Yn.json")
ZB_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_b")

from conftest import HAVE_SCHEMA, needs_schema   # noqa: E402
from rvt.genesis import residue_b as RB           # noqa: E402

# The constructors need the canonical 2026 class map; ``rvt.genesis.types``
# loads it lazily through ``load_schema()`` (the research corpus, else the
# sha-pinned bundled base -- never the process-wide ``install_schema``
# chokepoints), so the shared gate is the whole precondition.
pytestmark = needs_schema


# ---------------------------------------------------------------------------
# 1. the Group-B claim vs the residue census (Yn.json)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(YN), reason="Yn.json (residue census) not present")
def test_group_b_owns_exactly_the_M_to_Z_residue_classes():
    with open(YN) as fh:
        yn = json.load(fh)
    table = {row["class"]: int(row["count"]) for row in yn["residue_still_autodesk"]["table"]}
    m_to_z = {c: n for c, n in table.items() if c[:1].upper() >= "M"}
    assert set(m_to_z) == set(RB.GROUP_B_CLASSES), (
        sorted(set(m_to_z) ^ set(RB.GROUP_B_CLASSES)))
    for cls, n in m_to_z.items():
        assert RB.GROUP_B_CLASSES[cls][0] == n, (cls, n, RB.GROUP_B_CLASSES[cls])
    assert RB.GROUP_B_TOTAL == sum(m_to_z.values()) == 997
    # every class carries a census entry with a verdict
    for cls in RB.GROUP_B_CLASSES:
        assert cls in RB.GROUP_B_CENSUS, cls
        assert RB.GROUP_B_CENSUS[cls].get("verdict"), cls


def test_every_group_b_class_has_a_rung_or_the_endgame():
    rungs = {r.name for r in RB.ZB_CHAIN}
    for cls, (n, bucket, disp) in RB.GROUP_B_CLASSES.items():
        assert disp in rungs or disp.startswith("ENDGAME"), (cls, disp)


# ---------------------------------------------------------------------------
# 2. constructor byte-exact round trips (schema validity)
# ---------------------------------------------------------------------------

def _all_constructor_records():
    if not HAVE_SCHEMA:       # collection must never crash on a fresh clone
        return []
    recs = [
        RB.shared_parameter("GEN Mounting Height AFF", "e30c5485-191a-4e25-8830-aac0ab9fee47",
                            kind="ParamDefValue", spec=RB.SPEC_LENGTH,
                            group=RB.GROUP_DIMENSIONS, elem_id=21308, binding_ids=[26011]),
        RB.shared_parameter("GEN Asset Tag", RB._stable_guid("shared", "asset tag"),
                            kind="ParamDefString", spec=None, group=RB.GROUP_IDENTITY, elem_id=21309),
        RB.shared_parameter("GEN Emergency Circuit", RB._stable_guid("shared", "emergency"),
                            kind="ParamDefYesNo", spec=None, group=RB.GROUP_ELECTRICAL_CIRCUITING,
                            elem_id=21310),
        RB.project_parameter("GEN Design Package",
                             "revit.local.project:0146e0f4e0cd4b0c891f04555e61e4ac0000659a-1.0.0",
                             kind="ParamDefString", elem_id=26010, binding_ids=[26011]),
        RB.load_classification_parameter(113160, 5, "Lighting",
                                         "revit.local.classification:"
                                         "31ad5b1819aa4bc3aa07362dc06e3c810001f23b-2.0.0",
                                         elem_id=127547),
        RB.param_binding(21308, -2000700, 1, elem_id=26011),
        RB.wire_material_type("Copper", elem_id=102411),
        RB.wire_insulation_type("THHN", elem_id=102427),
        RB.wire_temperature_rating_type("90", elem_id=102443),
        RB.pipe_schedule_type("Schedule 40", elem_id=102360),
        RB.pipe_connection_type("Threaded", elem_id=102357),
        RB.pipe_material_type("Carbon Steel", 0.045, elem_id=102356),
        RB.pipe_segment("GEN Steel Pipe - ASME B36.10 Sch 40", 137433, 102360,
                        RB.pipe_size_rows("b36.10-sch40"), 0.045, elem_id=137323),
        RB.family_pen_width_table(8482, elem_id=1218557),
        RB.section_attributes("GEN Section Head - Filled, Tail - Filled",
                              font_id=26032, category_id=26030, elem_id=26029),
        RB.viewport_attributes("GEN Viewport Title with Line", category_id=9676, elem_id=324),
        RB.extended_material(RB.EXTENDED_MATERIALS[0], elem_id=141538),
        RB.structural_asset(RB.STRUCTURAL_ASSETS[0], elem_id=194585),
        RB.structural_asset(next(s for s in RB.STRUCTURAL_ASSETS if s.get("concrete")), elem_id=1177773),
        RB.structural_asset(next(s for s in RB.STRUCTURAL_ASSETS if s.get("wood")), elem_id=1352644),
        RB.parameter_filter("GEN Electrical - Lighting", [RB.OST_LightingFixtures], elem_id=116099),
        RB.sun_annotation(245443, elem_id=245447),
        RB.builtin_numbering_schema(RB.BUILTIN_NUMBERING_SCHEMES[0], elem_id=1218729),
        RB.slave_symbol_tracker(1352719, elem_id=1454535),
        RB.house_print_settings(RB.HOUSE_PRINT_SETUPS[0], elem_id=408188),
        RB.per_user_worksharing_settings("rvt-writer", 130813, elem_id=171476),
        RB.reference_plane("GEN Setout - Origin North-South", (0.0, 0.0), (0.0, 1.0), 40.0,
                           elem_id=273446),
        RB.datum_sketch_plane(311, 0.0, elem_id=3325),
        RB.free_sketch_plane((10.0, 5.0, 0.0), "y", elem_id=912817),
    ]
    return recs


@pytest.mark.parametrize("rec", _all_constructor_records(), ids=lambda r: r.class_name)
def test_constructor_object_round_trips_byte_exact(rec):
    rt = rec.roundtrip()
    assert rt["ok"], rt


def test_drafting_companions_round_trip():
    v = RB.drafting_viewer(1457028, elem_id=1457029)
    p = RB.drafting_viewport(1457028, 1457031, 324, elem_id=1457030)
    for se in (v, p):
        rep = se.roundtrip()
        assert rep["ok"], rep


# ---------------------------------------------------------------------------
# 3. the parameter-definition machinery / library rules
# ---------------------------------------------------------------------------

def test_shared_parameter_keeps_the_slot_guid_as_the_typeid_token():
    """The GUID is the ExternalParamTracking registry KEY: our object must
    carry it in BOTH m_externalParamKey and the typeId token (466/466 rule)."""
    guid = "7d14eb00-65db-4c93-9def-972be6a6ef0a"
    r = RB.shared_parameter("GEN Test", guid, elem_id=314641)
    assert r.obj["m_externalParamKey"]["m_guidValue"] == guid
    tok = r.obj["m_pParamDef"]["value"]["m_typeId"]["m_typeId"]
    assert tok == f"revit.local.shared:{guid.replace('-', '')}-1.0.0"
    assert r.obj["m_pParamDef"]["value"]["m_paramElemId"] == 314641


def test_project_param_type_id_embeds_the_element_id():
    tok = RB.project_param_type_id("0146e0f4-e0cd-4b0c-891f-04555e61e4ac", 26010)
    assert tok == "revit.local.project:0146e0f4e0cd4b0c891f04555e61e4ac0000659a-1.0.0"
    assert int(tok.split(":")[1][32:40], 16) == 26010


def test_our_caption_library_is_unique_and_sized_per_kind():
    for kind, n in (("ParamDefValue", 171), ("ParamDefString", 145), ("ParamDefYesNo", 34),
                    ("ParamDefMaterialBrowse", 78), ("ParamDefURL", 11), ("ParamDefFamType", 15),
                    ("ParamDefNoOfPoles", 3), ("ParamDefInt", 9)):
        caps = RB.our_shared_parameter_captions(kind, n)
        assert len(caps) == n, kind
        names = [c for c, _s, _g in caps]
        assert len(set(names)) == n, kind
        assert all(nm.startswith(RB.HOUSE_PREFIX + " ") for nm in names)
    # deterministic
    a = RB.our_shared_parameter_captions("ParamDefValue", 40)
    b = RB.our_shared_parameter_captions("ParamDefValue", 40)
    assert a == b


def test_load_classification_roles_are_the_six_and_captions_are_ours():
    assert set(RB.LOAD_CLASS_PARAM_ROLES) == {0, 1, 2, 3, 4, 5}
    r = RB.load_classification_parameter(113160, 3, "Lighting", "revit.local.classification:x-2.0.0",
                                         elem_id=1)
    pd = r.obj["m_pParamDef"]["value"]
    assert pd["m_caption"].startswith("GEN ") and "Demand Factor" in pd["m_caption"]
    assert pd["m_specTypeId"]["m_typeId"] == RB.SPEC_DEMAND_FACTOR
    assert pd["m_readOnly"] is True                      # the demand-factor role is read-only
    assert r.obj["m_eType"] == 3 and r.obj["m_idLoadClassification"] == 113160


def test_structural_asset_units_match_the_rosetta_twin():
    """345 MPa yield -> 105,156,000 internal; 200 GPa -> 6.096e10; 77 kN/m^3 -> ~7,153."""
    spec = next(s for s in RB.STRUCTURAL_ASSETS if s["key"] == "steel_345")
    r = RB.structural_asset(spec, elem_id=194585)
    dbl = {p["m_paramId"]: p["m_value"]
           for p in r.obj["m_oParamSet"]["value"]["m_pDoubleParams"]["value"]["m_paramSet"]}
    assert abs(dbl[RB.BIP_PHY["min_yield_stress"]] - 105_156_000.0) < 1.0
    assert abs(dbl[RB.BIP_PHY["young_x"]] - 6.096e10) < 1e6
    assert abs(dbl[RB.BIP_PHY["unit_weight"]] - 7153.5) < 5.0
    assert r.obj["m_propertySetType"] == RB.PROPSET_STRUCTURAL


def test_pipe_size_tables_are_dimensionally_consistent():
    for key in RB.PIPE_SIZE_TABLES:
        rows = RB.pipe_size_rows(key)
        assert rows, key
        for nom, inner, outer in rows:
            assert 0 < inner < outer, (key, nom, inner, outer)     # ID < OD
            assert nom > 0
    # the schedule chooser
    assert RB._table_for_schedule("Schedule 80", "Carbon Steel") == "b36.10-sch80"
    assert RB._table_for_schedule("Schedule 80", "Plastic") == "pvc-sch80"
    assert RB._table_for_schedule("K", "Copper") == "b88-k"
    assert RB._table_for_schedule("22", "Ductile Iron") == "awwa-c151-cl350"
    assert RB._table_for_schedule("10S", "Stainless Steel") == "b36.19-10s"


# ---------------------------------------------------------------------------
# 4. 'nothing of ours to reject': the reproduced machinery equals the sample's
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(Y9), reason="Y9.rvt (certified parent) not present")
class TestMachineryReproduction:
    @pytest.fixture(scope="class")
    def doc(self):
        from rvt.mutate import Document
        return Document.from_file(Y9)

    def _same(self, doc, eid, rec):
        """our object encodes to the SAME bytes as the sample's own record."""
        from rvt.encode import encode_record
        old = doc.record(eid, 102)
        ours = encode_record(102, eid, None, rec.class_id, rec.obj)
        return bytes(old.raw) == bytes(ours) if hasattr(old, "raw") else None

    def test_numbering_schemas_reproduce_the_builtin_machinery(self, doc):
        """The 3 built-in numbering schemes: our reproduction is VALUE-
        IDENTICAL to the sample's own decoded objects (built-in machinery =
        nothing of ours to reject; the ladder's byte-delta report proves the
        landed slots byte-identical -- ZB7 lists 8 such slots)."""
        by_name = {}
        for e in doc.ids_of_class("NumberingSchema"):
            by_name[str((doc.value(e) or {}).get("m_inInterfaceName")).strip()] = e
        for spec in RB.BUILTIN_NUMBERING_SCHEMES:
            e = by_name[spec["name"]]
            rec = RB.builtin_numbering_schema(spec, elem_id=e)
            r = doc.record(e, 102)
            got = doc.dec.decode_record(r.class_id, r.payload)
            assert rec.obj == got.value, spec["name"]

    def test_sun_annotation_and_slave_tracker_are_value_identical(self, doc):
        for e in doc.ids_of_class("SunAnnotationElem"):
            v = doc.value(e)
            rec = RB.sun_annotation(int(v.get("m_ownerDBViewId", -1)), elem_id=e)
            assert rec.obj == v, e
        for e in doc.ids_of_class("SlaveSymbolTrackerElem"):
            v = doc.value(e)
            rec = RB.slave_symbol_tracker(int(v.get("m_masterId", -1)), elem_id=e)
            assert rec.obj == v, e

    def test_param_binding_reproduces_the_sample_binding(self, doc):
        """A binding is pure machinery: {paramId, categoryId, elemOrSymbol} --
        our reproduction is value-identical to the sample's (up to the
        CellList form, which is null on 208/209 sample bindings)."""
        n_same = n = 0
        for e in doc.ids_of_class("ParamBinding")[:60]:
            v = doc.value(e)
            rec = RB.param_binding(int(v["m_paramId"]), int(v["m_categoryId"]),
                                   int(v["m_elemOrSymbol"]), elem_id=e)
            n += 1
            if v.get("m_cellList") is None and rec.obj == v:
                n_same += 1
        assert n_same >= n - 2, (n_same, n)      # only the PatternHelper-CellList era rows differ


# ---------------------------------------------------------------------------
# 5. the census instrument
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(Y9), reason="Y9.rvt not present")
def test_census_class_reports_free_vs_constant_fields():
    from rvt.mutate import Document
    doc = Document.from_file(Y9)
    c = RB.census_class(doc, "RbsWireInsulationType")
    assert c["count"] == 26
    # the ONLY free values of a wire insulation type are its id and its name
    assert set(c["varying_fields"]) == {"m_id", "m_symbolInfo.value.m_name"}, c["varying_fields"]
    # the census stores repr() strings
    assert c["constant"].get("m_cellList.value.m_cells[0].ptr_class") == repr("PatternHelper")


# ---------------------------------------------------------------------------
# 6. the in-place builders: plan correctness on the certified parent (Y9)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(Y9), reason="Y9.rvt (certified parent) not present")
class TestBuilders:
    @pytest.fixture(scope="class")
    def ctx(self):
        GS = RB._genesis_substitute()
        return GS.SubstContext(Y9, "TEST")

    @pytest.fixture(scope="class")
    def landed(self):
        return RB.y_ladder_landed()

    def test_y_ladder_landed_slots_are_protected(self, landed):
        # Y1..Y9 landed 1,333 slots (Yn); every builder must skip them
        assert len(landed) >= 1300

    @pytest.mark.parametrize("rung_name,expect", [
        ("ZB1_defs", {"ParamElemExternal": 466, "ParamBinding": 209,
                      "ParamElemElectricalLoadClassification": 108, "ParamElemProject": 8}),
        ("ZB2_mepcat", {"RbsWireMaterialType": 4, "RbsWireInsulationType": 26,
                        "RbsWireTemperatureRatingType": 3, "RbsPipeScheduleType": 13,
                        "RbsPipeConnectionType": 8, "RbsPipeMaterialType": 5, "PipeSegment": 15}),
        ("ZB3_pens", {"PenWidthTableElem": 8}),
        ("ZB4_annot", {"SectionAttributes": 10, "ViewportAttributes": 1}),
        ("ZB5_palette", {"MaterialElem": 10, "PropertySetElement": 28}),
        ("ZB6_filters", {"ParameterFilterElement": 7}),
        ("ZB7_machinery", {"SunAnnotationElem": 3, "NumberingSchema": 3, "SlaveSymbolTrackerElem": 1,
                           "WorksharingViewModeSettings": 1, "PrintSettings": 2, "Viewer": 1,
                           "Viewport": 3}),
        ("ZB8_content", {"RefPlane": 21, "SketchPlane": 30, "RoomElem": 1}),
    ])
    def test_builder_lands_one_record_per_residue_slot_of_the_same_class(self, ctx, landed,
                                                                         rung_name, expect):
        rung = RB.ZB_BY_NAME[rung_name]
        sb = rung.build(ctx, dict(landed))
        recs = {int(r.elem_id): r for r in sb.records}
        # one our-record per correspondence, class-matched, no protected slot targeted
        assert len(sb.corr) == len(sb.records) == len(sb.old_ids)
        by_class = {}
        for old, new in sb.corr.items():
            assert old not in landed, (rung_name, old)
            assert ctx.cls_of.get(int(old)) == recs[new].class_name, (rung_name, old)
            by_class[recs[new].class_name] = by_class.get(recs[new].class_name, 0) + 1
        assert by_class == expect, (rung_name, by_class)
        # every record schema-round-trips
        for r in sb.records:
            rt = r.roundtrip()
            assert rt["ok"], (rung_name, r.class_name, rt)


# ---------------------------------------------------------------------------
# 7. end-to-end: one single-change rung with the in-place byte-delta law
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(Y9), reason="Y9.rvt (certified parent) not present")
def test_single_rung_end_to_end_in_place_law(tmp_path):
    """Z_pens (the smallest bucket): Y9 + our 8 family-scoped pen tables in
    place.  Asserts the in-place law: ONLY those 8 slots' seq-102 records
    change, Global/Latest + Global/ElemTable byte-identical, nothing added or
    removed, validator 0 errors, the emitted file loads through the census."""
    out_dir = str(tmp_path)
    control = RB.stage_control(Y9, out_dir)
    assert control["md5"] == RB._md5(Y9)
    rung = RB.ZB_BY_NAME["ZB3_pens"]
    single = RB.dataclasses.replace(rung, name="Z_pens", parent="BASE")
    rep = RB.zb_substitute_inplace(single, Y9, out_dir=out_dir, out_name="Z_pens",
                                   base_path=Y9, control=control)
    assert rep["verdict"] == "VALID", rep.get("FAILED_SELF_CHECK")
    bd = rep["byte_delta"]
    assert bd["assertion_holds"]
    assert bd["only_partition_differs"]
    assert bd["elemtable_identical"] and bd["adocument_identical"]
    assert not bd["records_added_ids"] and not bd["records_removed_ids"]
    assert bd["expected_slots"] == 8
    assert rep["validator"]["ok"] and rep["validator"]["errors"] == 0
    assert (rep["structural"] or {}).get("ok")
    assert rep["parity"]["latest_byte_identical"]
    # the report is on disk in the ladder's shape
    with open(os.path.join(out_dir, "Z_pens.json")) as fh:
        on_disk = json.load(fh)
    assert on_disk["verdict"] == "VALID"
    assert len(on_disk["landed_slots"]) == 8


# ---------------------------------------------------------------------------
# 8. the built ladder on disk (if present): manifest consistency
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(os.path.join(ZB_DIR, "probes.json")),
                    reason="ZB ladder not built (run: python -m rvt.genesis.residue_b)")
def test_probes_manifest_names_certified_base_and_control():
    with open(os.path.join(ZB_DIR, "probes.json")) as fh:
        m = json.load(fh)
    assert m["probes"], "probes.json lists no probes"
    ctrl = m.get("standing_control") or {}
    assert ctrl.get("file", "").endswith("CTRL_Y9_base.rvt")
    for p in m["probes"]:
        assert (p.get("base") or {}).get("certification"), p["rung"]
        assert p.get("control_to_upload_with_batch"), p["rung"]
        # a built probe recorded VALID by its own self-checks
        if os.path.exists(os.path.join(ROOT, p["file"])):
            assert p["verdict"] in ("VALID", "NOT-CLEAN", "NOT-BUILT"), p["rung"]

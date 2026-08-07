"""tests/test_port2023.py -- the genesis-2023 constructor portability layer.

Proves (1) the 32-BIT-ID MODEL: the schema-declared id width, the 2023
record framing (4-byte headers / sentinel), the 28-byte ElemTable rows
verified against the schema-directed decode, and the id32 context's
swap-and-restore semantics; (2) the CONFIRMED four-way portability verdicts
-- including every place 2023 evolved DIFFERENTLY from 2024 AND 2025
(DBViewDrafting without 2024's m_scheduleInstanceIds, Viewport v10 !=
2024's v10, the ParamDef group re-typing, the ElectricalLoadClassification
bool split, the duct-settings extra drop, the reorder wave, the machinery
deltas ElemTable / GRep); (3) the field-map hooks and every delegation
precondition (port2025 numbering hooks only because 2023==2025 there;
port2024 autocam/duct/tracker hooks only because 2023==2024 there --
asserted, not assumed); (4) adapt() round-trips byte-exact under the 2023
codec, matches the 2023 corpus field shape, and the specimen gate is
BYTE-EXACT against Autodesk's own 2023 sample records; (5) missing classes
are refused honestly.  Sample-backed assertions skip cleanly off the dev
machine.
"""
import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.genesis import port2023 as P23                              # noqa: E402
from rvt.genesis import port2024 as P24                              # noqa: E402
from rvt.genesis import port2025 as P25                              # noqa: E402
from rvt.genesis import types as T                                   # noqa: E402
from rvt.genesis.types import INVALID                                # noqa: E402

RST23 = os.path.join(ROOT, "samples", "2023", "rstbasicsampleproject.rvt")
needs_sample = pytest.mark.skipif(not os.path.exists(RST23),
                                  reason="quarantined 2023 samples not present")


# ---------------------------------------------------------------------------
# 1. the 32-bit-id model
# ---------------------------------------------------------------------------
@needs_sample
def test_id_width_is_schema_declared():
    _d23, _e23, s23 = P23._S23()
    _d26, _e26, s26 = P23._S26()
    assert P23.id_width_from_schema(s23) == 4
    assert P23.id_width_from_schema(s26) == 8
    idf = s23.by_name["Identifier"].fields[0]
    assert (idf.name, idf.kind) == ("m_id", 0x04)
    idf26 = s26.by_name["Identifier"].fields[0]
    assert (idf26.name, idf26.kind) == ("m_id64", 0x0B)


def test_iter_records_2023_framing_and_sentinel():
    """Synthetic segment: one seq-102 record (4-byte id, stamp, psize,
    class word, body, psize repeat) + the 4-byte -1 sentinel."""
    body = b"\xAA\xBB"
    ps = 2 + len(body)
    seg = (struct.pack("<iII", 42, 7, ps) + struct.pack("<H", 0x123) + body
           + struct.pack("<I", ps))
    seg += struct.pack("<iII", -1, 1, 0) + struct.pack("<I", 0)
    recs = list(P23.iter_records_2023(seg, 102))
    assert len(recs) == 2
    assert (recs[0].elem_id, recs[0].stamp, recs[0].class_id) == (42, 7, 0x123)
    assert recs[0].payload == body and recs[0].trailer_ok
    assert (recs[1].elem_id, recs[1].body_size) == (-1, 0)
    # seq-101: 8-byte header, no stamp
    seg1 = (struct.pack("<iI", 43, ps) + struct.pack("<H", 0x124) + body
            + struct.pack("<I", ps))
    r1 = list(P23.iter_records_2023(seg1, 101))
    assert len(r1) == 1 and r1[0].elem_id == 43 and r1[0].stamp == 0


def test_id32_swaps_and_restores():
    from rvt import encode as E
    from rvt import objects as O
    before_rd, before_wr = O.Reader.element_id, E.Writer.element_id
    with P23.id32():
        rd = O.Reader(struct.pack("<i", -7) + b"\x00" * 4)
        assert rd.element_id() == -7 and rd.p == 4          # 4 bytes, not 8
        w = E.Writer()
        w.element_id(-7)
        assert w.bytes() == struct.pack("<i", -7)
        with P23.id32():                                     # re-entrant
            rd2 = O.Reader(struct.pack("<i", 5))
            assert rd2.element_id() == 5
    assert O.Reader.element_id is before_rd
    assert E.Writer.element_id is before_wr
    rd = O.Reader(struct.pack("<q", -7))
    assert rd.element_id() == -7 and rd.p == 8              # restored to i64


@needs_sample
def test_elemtable_2023_matches_schema_directed_decode():
    """The fixed-width 28-byte-row parser must agree with the schema-directed
    id32 decode of the whole Global/ElemTable stream."""
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream
    with open_rvt(RST23) as f:
        st = inflate_global_stream(f.raw("Global/ElemTable"))
    tbl = P23.parse_elemtable_2023(st.payload, "rst2023")
    dec, _enc, _s = P23._S23()
    class_tag = struct.unpack_from("<H", st.payload, 0)[0]
    with P23.id32():
        got = dec.decode_record(class_tag, st.payload[2:])
    arr = got.value["m_elemArr"]
    assert len(arr) == len(tbl.records) == tbl.count
    for i in (0, 1, len(arr) // 2, len(arr) - 1):
        d, r = arr[i], tbl.records[i]
        assert d["m_id"] == r.id
        assert d["m_history"]["m_originalElementId"]["m_id"] == r.original_id
        assert d["m_partitionId"]["m_id"] == r.partition_id
        own = d["m_OwningElementId"]
        assert (own == -1 and r.owner_id == 0xFFFFFFFFFFFFFFFF) or own == r.owner_id
    assert got.value["m_pSource"]["value"]["m_last"] == tbl.footer.last_id
    assert tbl.footer.last_id == max(r.id for r in tbl.records)


@needs_sample
def test_full_2023_read_stack_parity():
    """Document.from_file under reading_2023: every element decodes at the
    known parity rate; ids are 32-bit-plausible; the id watermark holds."""
    doc = P23.load_document_2023(RST23)
    assert len(doc.et.records) == 13_821
    assert doc.et.footer.last_id == 1_472_302
    with P23.id32():
        v = doc.value(2) or {}                              # the pen table
        assert v.get("m_famId") == -1
        assert doc.class_of(2) == "PenWidthTableElem"


# ---------------------------------------------------------------------------
# 2. the CONFIRMED portability verdicts (four-way)
# ---------------------------------------------------------------------------
@needs_sample
def test_missing_2023_includes_both_inherited_and_new_classes():
    for n in P23.MISSING_2023_CONSTRUCTED:
        assert not P23.exists_2023(n), n
        assert P23.diff_class(n)["verdict"] == "MISSING-2023", n
    # the 2023-NEW missing classes exist in 2024:
    for n in ("FabricationServiceSettings", "SSEPointVisibilitySettings"):
        assert P24.exists_2024(n), n
    # DrawOrderMgrBase: missing but never constructed; its fields moved onto
    # DrawOrderMgr, which exists
    assert P23.diff_class("DrawOrderMgrBase")["verdict"] == "MISSING-2023"
    assert P23.exists_2023("DrawOrderMgr")
    _d, _e, s23 = P23._S23()
    dom = {f.name for f in s23.by_name["DrawOrderMgr"].fields}
    assert {"m_pADoc", "m_pDBView", "m_aDrawOrder"} <= dom


@needs_sample
def test_machinery_layer_ports():
    for n in ("Element", "Symbol", "SerializedDummy", "PartitionTable",
              "DocumentIncrementTable", "GStyleElem", "CategoryElem", "Level"):
        assert P23.diff_class(n)["verdict"] == "IDENTICAL", n
    assert P23.diff_class("ElementHeader")["verdict"] == "VERSION-ONLY"
    # the 2023-only machinery deltas (2026-only field drops; free)
    et = P23.diff_class("ElemTable")
    assert et["verdict"] == "LAYOUT-DELTA"
    assert et["deltas"][0]["only_2026"] == ["m_bLastElementIdOverride"]
    ge = P23.diff_class("GElement")
    assert ge["verdict"] == "LAYOUT-DELTA"
    assert any(d["base"] == "GRep" and d["only_2026"] == ["m_elementId"]
               for d in ge["deltas"])


@needs_sample
def test_known_movers_established_independently():
    """The charter's known-mover classes, each measured for 2023 (never
    assumed from 2024/2025)."""
    # DBView: m_viewPositionId drop + reorder, hits every view subclass
    dv = P23.diff_class("DBView")
    d = next(x for x in dv["deltas"] if x["base"] == "DBView")
    assert "m_viewPositionId" in d["only_2026"] and d.get("order_differs")
    # DBViewDrafting: two 2026-only drops, NO 2024-only m_scheduleInstanceIds
    dd = P23.diff_class("DBViewDrafting")
    own = next(x for x in dd["deltas"] if x["base"] == "DBViewDrafting")
    assert set(own["only_2026"]) == {"m_sheetCollectionId", "m_sheetTitleBlockId"}
    assert own["only_2023"] == []
    d24 = P24.diff_class("DBViewDrafting")
    own24 = next(x for x in d24["deltas"] if x["base"] == "DBViewDrafting")
    assert "m_scheduleInstanceIds" in own24["only_2024"]     # 2024-only field
    # Viewport: v10 in BOTH 2023 and 2024 with DIFFERENT layouts
    vp = P23.diff_class("Viewport")
    own = next(x for x in vp["deltas"] if x["base"] == "Viewport")
    assert set(own["only_2026"]) == {"m_viewPosition", "m_viewAnchor",
                                     "m_oPlaceholderBoxOutline"}
    assert vp["version_2023"] == 10
    _d24, _e24, s24 = P24._S24()
    assert s24.by_name["Viewport"].version == 10
    assert any(f.name == "m_oPlaceholderBoxOutline"
               for f in s24.by_name["Viewport"].fields)
    _d23, _e23, s23 = P23._S23()
    assert not any(f.name == "m_oPlaceholderBoxOutline"
                   for f in s23.by_name["Viewport"].fields)
    # BrowserOrganizationTracking: the same three-field split as 2024/2025
    bt = P23.diff_class("BrowserOrganizationTracking")
    own = next(x for x in bt["deltas"] if x["base"] == "BrowserOrganizationTracking")
    assert set(own["only_2023"]) == {"m_currentBrOrgViews", "m_currentBrOrgSheets",
                                     "m_currentBrOrgSchedules"}
    # GeomTable: the two 2023-only ints
    gt = P23.diff_class("GeomTable")
    own = next(x for x in gt["deltas"] if x["base"] == "GeomTable")
    assert set(own["only_2023"]) == {"m_maxSafeTag",
                                     "m_lastCheckedKingsUserModificationDate"}
    # wire/conductor: catalog missing; RbsWireType id->string
    wt = P23.diff_class("RbsWireType")
    own = next(x for x in wt["deltas"] if x["base"] == "RbsWireType")
    assert own["only_2026"] == ["m_idMaxConductorSize"]
    assert own["only_2023"] == ["m_strMaxConductorSize"]


@needs_sample
def test_2023_new_deltas():
    # ParamDef: group ForgeTypeId -> group ElementId (identical in 2024/2025)
    pd = P23.diff_class("ParamDef")
    own = next(x for x in pd["deltas"] if x["base"] == "ParamDef")
    assert own["only_2026"] == ["m_groupTypeId"]
    assert own["only_2023"] == ["m_groupElemId"]
    assert P24.diff_class("ParamDef")["verdict"] == "IDENTICAL"
    # ElectricalLoadClassification: int enum -> two bools
    lc = P23.diff_class("ElectricalLoadClassification")
    own = next(x for x in lc["deltas"] if x["base"] == "ElectricalLoadClassification")
    assert own["only_2026"] == ["m_signitureType"]
    assert set(own["only_2023"]) == {"m_motor", "m_spare"}
    assert P24.diff_class("ElectricalLoadClassification")["verdict"] == "IDENTICAL"
    # the reorder wave: same field set, different order, often same version
    mt = P23.diff_class("Material")
    own = next(x for x in mt["deltas"] if x["base"] == "Material")
    assert own["only_2026"] == [] and own["only_2023"] == [] and own["order_differs"]
    assert mt["version_2026"] == mt["version_2023"] == 13
    assert P24.diff_class("Material")["verdict"] == "IDENTICAL"
    # GeomStep: absent-not-renamed, like 2024 (no rename hook must exist)
    gs = P23.diff_class("VertCompoundStructureGStep")
    own = next(x for x in gs["deltas"] if x["base"] == "GeomStep")
    assert own["only_2026"] == ["m_oExtraDatas"] and own["only_2023"] == []
    assert ("GeomStep", "m_oExtraData") not in P23.HOOKS_2023
    # RbsDuctSettingsElem: 2024's rename PLUS an extra 2026-only drop
    ds = P23.diff_class("RbsDuctSettingsElem")
    own = next(x for x in ds["deltas"] if x["base"] == "RbsDuctSettingsElem")
    assert set(own["only_2026"]) == {"m_airDynamicViscosity",
                                     "m_enableNetworkBasedCalculations"}
    assert own["only_2023"] == ["m_dAirViscosity"]


@needs_sample
def test_delegation_preconditions():
    """Every delegated hook's layout precondition, asserted."""
    d23, _e23, s23 = P23._S23()
    d25, _e25, s25 = P25._S25()
    d24, _e24, s24 = P24._S24()
    # numbering hooks (port2025): 2023 == 2025 layouts
    for cls in ("ParameterBasedPartitionDescriptionCreator", "NumberingSchemaType",
                "ControlledConstDocAccess"):
        f23 = [(c.name, P23._field_sig(f, s23)) for c in d23.chain(s23.by_name[cls].type_id)
               for f in c.fields]
        f25 = [(c.name, P25._field_sig(f, s25)) for c in d25.chain(s25.by_name[cls].type_id)
               for f in c.fields]
        assert f23 == f25, cls
    assert P23.NUMBERING_SCHEMA_TYPE_GUIDS_2023 == P25.NUMBERING_SCHEMA_TYPE_GUIDS_2025
    # autocam hooks (port2024): 2023 == 2024 own-field layout
    f23 = [P23._field_sig(f, s23) for f in s23.by_name["AutoCamSettingsElem"].fields]
    f24 = [P24._field_sig(f, s24) for f in s24.by_name["AutoCamSettingsElem"].fields]
    assert f23 == f24
    # duct + tracker hooks (port2024): the hooked 2023 field's signature
    # equals the 2024 one
    for cls, fname in (("RbsDuctSettingsElem", "m_dAirViscosity"),
                       ("MEPNetworkTracker", "m_component2BaseElementMap")):
        g23 = next(P23._field_sig(f, s23) for f in s23.by_name[cls].fields
                   if f.name == fname)
        g24 = next(P24._field_sig(f, s24) for f in s24.by_name[cls].fields
                   if f.name == fname)
        assert g23 == g24, (cls, fname)


@needs_sample
def test_every_2023_only_field_of_constructed_deltas_is_covered():
    """For each delta class genesis constructs, every 2023-only field is
    either hooked or its 2023 blank default is the corpus value."""
    hooked = {f for (_c, f) in P23.HOOKS_2023}
    blank_ok = {
        "m_bMassShellExcluded",    # Icky wrapper: False 19/19 rst specimens
        "m_pADoc", "m_pDBView",    # DrawOrderMgr: carried by NAME from the
                                   # skeleton's own pointer body (45/45 rst
                                   # views carry the same shape)
    }
    for cls in ("GeomTable", "RbsWireType", "RbsWireSettingsElem", "NumberingSchema",
                "BrowserOrganization", "ModelGraphicsStyle", "ViewDisplayMgr",
                "ReinforcementSettings", "VertCompoundStructureGStep",
                "AutoCamSettingsElem", "RbsDuctSettingsElem", "MEPNetworkTracker",
                "RbsDistributionSysType", "DBViewDrafting", "DBView3d",
                "DBViewPlan", "Viewport", "BrowserOrganizationTracking",
                "ParamDefValue", "ParamDefString", "ElectricalLoadClassification",
                "ElemTable", "GElement", "StructSettingsElem", "KeynoteTable",
                "AssemblyCodeTable", "RbsWireSizesElem"):
        d = P23.diff_class(cls)
        for x in d.get("deltas", []):
            for f in (x.get("only_2023") or []):
                assert f in hooked or f in blank_ok, f"{cls}.{f} not covered"


@needs_sample
def test_class_id_2023_matches_framing_ordinals():
    """By-name resolution == the module pin == the reduce stream's
    KNOWN_RELEASES[2023] entry (landed mid-stream; two independent
    measurements cross-checked)."""
    from rvt import versions
    for const, cls in versions.FRAMING_CLASSES.items():
        assert P23.class_id_2023(cls) == P23.FRAMING_2023[const], (const, cls)
    rel = versions.KNOWN_RELEASES.get(2023)
    if rel is not None:
        assert dict(rel.framing) == P23.FRAMING_2023
        assert rel.schema_sha256 == P23.SCHEMA_SHA256_2023
        assert rel.schema_size == P23.SCHEMA_SIZE_2023
        assert rel.class_count == P23.CLASS_COUNT_2023
        for name, ordinal in rel.anchors.items():
            assert P23.class_id_2023(name) == ordinal, name


@needs_sample
def test_reference_elemtable_parser_agrees_with_records32_on_corpus():
    """port2023's schema-ordered reference parser and records32's parser
    must agree on every corpus row (id == original_id throughout -- the
    property that makes the two orders byte-indistinguishable today)."""
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream
    from rvt.versions import records32
    with open_rvt(RST23) as f:
        st = inflate_global_stream(f.raw("Global/ElemTable"))
    a = P23.parse_elemtable_2023(st.payload, "ref")
    b = records32.parse_elemtable32(st.payload, "r32")
    assert len(a.records) == len(b.records)
    for ra, rb in zip(a.records, b.records):
        assert ra.id == ra.original_id, "corpus premise broken: id != orig"
        assert (ra.id, ra.creation_ep, ra.modified_ep, ra.user_modified_ep,
                ra.partition_id, ra.owner_id) == \
               (rb.id, rb.creation_ep, rb.modified_ep, rb.user_modified_ep,
                rb.partition_id, rb.owner_id)
    assert a.footer.last_id == b.footer.last_id


@needs_sample
def test_frozen_table_exists_and_agrees():
    tab = P23.portability_table(write=True)
    assert tab["counts"].get("MISSING-2023", 0) >= 16
    assert tab["counts"].get("LAYOUT-DELTA", 0) >= 100
    assert tab["counts"].get("VERSION-ONLY", 0) >= 3
    assert os.path.exists(P23.PORTABILITY_JSON)
    nm = tab["non_monotonic_findings"]
    assert len(nm["reorder_only_classes"]) >= 40
    assert "Material" in nm["reorder_only_classes"]
    for n in ("DBViewDrafting", "Viewport", "RbsDuctSettingsElem"):
        assert n in nm["deltas_that_differ_from_2024"], n
    assert tab["id_model"]["element_id_bytes"] == 4


# ---------------------------------------------------------------------------
# 3. adapt(): field maps + round-trip gate
# ---------------------------------------------------------------------------
@needs_sample
def test_adapt_wall_type_roundtrips_and_drops_geomstep_extras():
    rec = T.new_wall_type("PT Wall", [("structure", 200, INVALID)], elem_id=9300001)
    pr = P23.adapt_record(rec)
    assert pr.class_id == P23.class_id_2023("BasicWallType")
    v = P23.verify_ported(pr)
    assert v["ok"], v
    step = pr.obj["m_geomSteps"]["value"]["m_bRepFormGList"][0]["value"]
    assert "m_oExtraData" not in step and "m_oExtraDatas" not in step


@needs_sample
def test_adapt_fill_pattern_geomtable_gets_mined_defaults():
    rec = T.new_fill_pattern("PT Solid", [], elem_id=9300002)
    pr = P23.adapt_record(rec)
    gt = pr.obj["m_pGeomTable"]["value"]
    assert gt["m_maxSafeTag"] == -1
    assert gt["m_lastCheckedKingsUserModificationDate"] == -1
    assert P23.verify_ported(pr)["ok"]


@needs_sample
def test_adapt_wire_type_writes_size_string():
    rec = T.new_wire_type("PT THWN", max_size_id=9300050, elem_id=9300003)
    pr = P23.adapt_record(rec, resolve_name=lambda i: "500" if i == 9300050 else None)
    assert pr.obj["m_strMaxConductorSize"] == "500"
    assert "m_idMaxConductorSize" not in pr.obj
    pr2 = P23.adapt_record(T.new_wire_type("PT2", elem_id=9300004))
    assert pr2.obj["m_strMaxConductorSize"] == P23.WIRE_MAX_SIZE_FALLBACK_2023
    assert P23.verify_ported(pr)["ok"] and P23.verify_ported(pr2)["ok"]


@needs_sample
def test_adapt_wire_settings_gets_mined_doubles():
    from rvt.genesis import settings as st
    pr = P23.adapt_record(st.wire_settings(elem_id=9300005))
    for k, want in P23.WIRE_SETTINGS_2023.items():
        assert pr.obj[k] == want, k
    assert P23.verify_ported(pr)["ok"]


@needs_sample
def test_adapt_param_def_group_map():
    from rvt.genesis.residue_b import GROUP_DIMENSIONS, GROUP_GENERAL, shared_parameter
    rec = shared_parameter("PT Len", "12345678-1234-1234-1234-123456789abc",
                           group=GROUP_DIMENSIONS, elem_id=9300006)
    pr = P23.adapt_record(rec)
    pd = pr.obj["m_pParamDef"]["value"]
    assert pd["m_groupElemId"] == -5000101                   # dimensions
    assert "m_groupTypeId" not in pd
    assert P23.verify_ported(pr)["ok"]
    # unwitnessed token -> -1 with a note
    rec2 = shared_parameter("PT Gen", "12345678-1234-1234-1234-123456789abd",
                            group=GROUP_GENERAL, elem_id=9300007)
    pr2 = P23.adapt_record(rec2)
    assert pr2.obj["m_pParamDef"]["value"]["m_groupElemId"] == -1
    assert any("not witnessed" in n for n in pr2.notes)
    assert P23.verify_ported(pr2)["ok"]


@needs_sample
def test_adapt_load_classification_bool_split():
    """m_signitureType (1 motor / 2 other / 3 spare / 0) -> the 2023 bools,
    the exact mapping the 2023 rme corpus witnesses (defaults_2023.json)."""
    base = T.blank_object("ElectricalLoadClassification")
    for name, sig in (("Motor", 1), ("Spare", 3), ("Other", 2), ("HVAC", 0)):
        obj = dict(base)
        obj["m_name"] = name
        obj["m_signitureType"] = sig
        a23 = P23.adapt("ElectricalLoadClassification", obj)
        assert a23["m_motor"] is (sig == 1), name
        assert a23["m_spare"] is (sig == 3), name
        assert "m_signitureType" not in a23


@needs_sample
def test_adapt_autocam_renames_via_port2024_delegation():
    from rvt.genesis import settings as st
    src = st.auto_cam_settings(elem_id=9300008)
    pr = P23.adapt_record(src)
    for dst, srcname in P24.AUTOCAM_RENAMES_2024.items():
        assert pr.obj[dst] == list(src.obj[srcname]), dst
        assert srcname not in pr.obj
    assert P23.verify_ported(pr)["ok"]


@needs_sample
def test_adapt_duct_settings_kinematic_and_extra_drop():
    from rvt.genesis import settings as st
    src = st.duct_settings(elem_id=9300009)
    pr = P23.adapt_record(src)
    mu = src.obj["m_airDynamicViscosity"]
    rho = src.obj["m_dAirDensity"]
    assert pr.obj["m_dAirViscosity"] == mu / rho
    assert "m_enableNetworkBasedCalculations" not in pr.obj
    assert P23.verify_ported(pr)["ok"]


@needs_sample
def test_adapt_view_drafting_and_draw_order_carry():
    """The skeleton's DBView base object adapted onto 2023's DBViewDrafting
    chain: the two 2026-only sheet fields drop, 2024-only
    m_scheduleInstanceIds never appears, and the DrawOrderMgr pointer's
    fields (on the MISSING DrawOrderMgrBase in 2026; on DrawOrderMgr itself
    in 2023) carry by name -- then the whole view round-trips."""
    from rvt.genesis.skeleton import dbview_base
    obj = dbview_base(9300200, "PT Drafting", viewer_id=9300201,
                      drawing_id=9300202, sun_settings_id=9300203)
    a23 = P23.adapt("DBViewDrafting", obj)
    assert "m_viewPositionId" not in a23                     # DBView 2026-only
    assert "m_sheetTitleBlockId" not in a23
    assert "m_sheetCollectionId" not in a23
    assert "m_scheduleInstanceIds" not in a23                # 2024-only
    dom = a23.get("m_pDetailDrawOrderMgr")
    assert dom and dom["value"].get("m_pADoc") == {"weakref": 1}
    assert dom["value"].get("m_pDBView") == {"weakref": 2}
    assert dom["value"].get("m_aDrawOrder") == []
    v = P23.verify_roundtrip_2023(P23.class_id_2023("DBViewDrafting"), a23)
    assert v["ok"], v


@needs_sample
def test_adapt_refuses_missing_2023_constructors():
    from rvt.genesis import settings as st
    with pytest.raises(P23.Missing2023):
        P23.adapt_record(T.new_conductor_size("12", 2.05, elem_id=9300010))
    with pytest.raises(P23.Missing2023):
        P23.adapt_record(st.sse_point_visibility_settings(elem_id=9300011))
    with pytest.raises(P23.Missing2023):
        P23.adapt_record(st.tracker("MEPNetworkDataElem", elem_id=9300012))


@needs_sample
def test_adapt_rejects_ids_beyond_32_bits():
    rec = T.new_wall_type("PT Wide", [("structure", 200, INVALID)],
                          elem_id=2**31 + 5)
    with pytest.raises(P23.PortabilityError):
        P23.adapt_record(rec)


@needs_sample
def test_selftest_battery_green():
    rep = P23.selftest(verbose=False)
    assert rep["ok"], {k: v for k, v in rep.items() if k != "records"}
    assert all(r["refused"] for r in rep["refusals"] if "refused" in r)


# ---------------------------------------------------------------------------
# 4. sample-backed corpus-shape parity + specimen byte gate
# ---------------------------------------------------------------------------
@needs_sample
def test_adapted_shapes_match_2023_corpus():
    """Key-set parity: the adapted object's field keys must equal a decoded
    2023 sample record's keys for the same class."""
    doc = P23.load_document_2023(RST23)
    from rvt.genesis import settings as st

    with P23.id32():
        def sample_keys(cls):
            ids = doc.ids_of_class(cls, host_only=True)
            return set((doc.value(ids[0]) or {}).keys()) if ids else None

        pairs = [
            ("BasicWallType", P23.adapt_record(
                T.new_wall_type("PT", [("structure", 200, INVALID)], elem_id=9300020)).obj),
            ("RbsWireType", P23.adapt_record(
                T.new_wire_type("PT", elem_id=9300021)).obj),
            ("RbsWireSettingsElem", P23.adapt_record(
                st.wire_settings(elem_id=9300022)).obj),
            ("BrowserOrganization", P23.adapt_record(
                st.browser_organization("all", elem_id=9300023)).obj),
            ("AutoCamSettingsElem", P23.adapt_record(
                st.auto_cam_settings(elem_id=9300024)).obj),
            ("RbsDuctSettingsElem", P23.adapt_record(
                st.duct_settings(elem_id=9300025)).obj),
            ("MEPNetworkTracker", P23.adapt_record(
                st.tracker("MEPNetworkTracker", elem_id=9300026)).obj),
        ]
        from rvt.genesis.residue_b import (BUILTIN_NUMBERING_SCHEMES,
                                           builtin_numbering_schema)
        pairs.append(("NumberingSchema", P23.adapt_record(
            builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], elem_id=9300027)).obj))
        for cls, ours in pairs:
            want = sample_keys(cls)
            if want is None:
                continue
            assert set(ours.keys()) == want, (cls, set(ours) ^ want)


@needs_sample
def test_specimen_byte_level_gate():
    """OUR adapted constructors byte-exact vs Autodesk's own 2023 records
    (auto-cam / MEP tracker / pen-table layout), plus specimen re-encode
    round-trips for every ported class -- 32-bit ids included."""
    rep = P23.verify_specimen_byte_level(verbose=False)
    assert rep["ok"], rep
    assert rep["AutoCamSettingsElem"]["byte_exact"]
    assert rep["MEPNetworkTracker"]["byte_exact"]
    assert rep["PenWidthTableElem"]["byte_exact"]
    rts = rep["specimen_roundtrips"]
    missing = [c for c, r in rts.items() if r == "no-specimen"]
    assert not missing, f"specimen list stale: {missing}"


@needs_sample
def test_frozen_miners_are_coherent():
    """The frozen 2023 miner artifacts: derivable, self-consistent, and the
    format constants match the 2026 constructor constants."""
    from rvt.genesis.settings import PEN_COUNT, PEN_SCALE_BREAKPOINTS
    res = P23.mine_all(verbose=False)
    enum = res[os.path.basename(P23.ENUM_2023_JSON)]
    prof = res[os.path.basename(P23.PROFILE_2023_JSON)]
    pen = res[os.path.basename(P23.PEN_2023_JSON)]
    pal = res[os.path.basename(P23.PALETTE_2023_JSON)]
    dfl = res[os.path.basename(P23.DEFAULTS_2023_JSON)]
    assert enum["count"] >= 1000 and enum["cuttable"] >= 300
    assert {c["id"] for c in enum["categories"]} >= {-2000011, -2000032}  # walls, floors
    assert prof["count"] >= 1300 and prof["rows_analysed"] >= 4000
    assert pen["scale_breakpoints"] == PEN_SCALE_BREAKPOINTS == \
        P23.PEN_SCALE_BREAKPOINTS_2023
    assert pen["pens_per_vector"] == PEN_COUNT == P23.PEN_COUNT_2023
    assert pal["laws_hold"] is True
    assert dfl["geomtable_dominant"] == [-1, -1]
    assert set(P23.PARAM_GROUP_ELEM_2023.values()) <= \
        {int(k) for k in dfl["param_group_witnesses"]}
    lc = dfl["load_classifications"]
    assert lc["Motor"]["motor"] is True and lc["Spare"]["spare"] is True


@needs_sample
def test_enum_2023_vs_2026_relationship():
    """The 2023 category enum must be a near-subset of the 2026 one with
    identical cuttability on the shared ids (the 2024/2025 pattern)."""
    enum23, _ = P23.load_2023_catalog_constants()
    from rvt.genesis.catalog import load_builtin_category_enum
    e26 = load_builtin_category_enum()
    cut26 = {c["id"]: c["cut"] for c in e26["categories"]}
    cut23 = {c["id"]: c["cut"] for c in enum23["categories"]}
    shared = set(cut23) & set(cut26)
    assert len(shared) >= 1000
    diff = [i for i in shared if cut23[i] != cut26[i]]
    assert not diff, f"cuttability differs on {len(diff)} shared ids: {diff[:8]}"

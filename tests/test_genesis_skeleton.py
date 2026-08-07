"""Tests for rvt.genesis.skeleton -- the document scaffolding constructors.

Three tiers of evidence:

1. BYTE-EXACT SPECIMEN RECONSTRUCTION: build a skeleton object FROM SCRATCH
   with a constructor (only plain parameter values, no cloning), encode it
   with the schema encoder, and compare against the ORIGINAL record bytes of
   the equivalent element in ``rstbasicsampleproject`` (stamp included).
   Proves the constructors reproduce Revit's own serialization.
2. WHOLE-SKELETON encode -> decode round trip: every constructed record is
   schema-valid and byte-stable (126 records).
3. GLOBAL TABLE STREAMS: the six minimal models encode with
   ``rvt.stream_encoders`` and decode back to themselves; the cross-stream
   save invariants of KNOWLEDGE.md hold by construction.

Corpus-dependent tests skip when ``extracted/`` (or the schema) is absent.
"""
from __future__ import annotations

import os
import struct
import zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, "extracted")
SAMPLE = "rstbasicsampleproject"
HAVE_CORPUS = os.path.isdir(os.path.join(EXTRACTED, SAMPLE))
HAVE_SCHEMA = os.path.exists(os.path.join(
    EXTRACTED, "racbasicsampleproject", "Formats__Latest.gz", "000.bin"))

# rvt.genesis.__init__ may import sibling streams' modules; import the
# skeleton module directly so this file never depends on their presence.
import importlib.util
_SPEC = importlib.util.spec_from_file_location(
    "rvt.genesis.skeleton",
    os.path.join(ROOT, "src", "rvt", "genesis", "skeleton.py"))
sk = importlib.util.module_from_spec(_SPEC)
try:
    from rvt.genesis import skeleton as sk       # normal path
except Exception:                                  # pragma: no cover
    assert _SPEC and _SPEC.loader
    _SPEC.loader.exec_module(sk)

needs_corpus = pytest.mark.skipif(not HAVE_CORPUS, reason="extracted corpus absent")
needs_schema = pytest.mark.skipif(not HAVE_SCHEMA, reason="schema blob absent")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def doc():
    from rvt.mutate import Document
    return Document.load(SAMPLE)


@pytest.fixture(scope="module")
def enc(doc):
    from rvt.encode import ObjectEncoder
    return ObjectEncoder(decoder=doc.dec)


def _original_record(doc, eid: int, seq: int) -> bytes:
    from rvt.encode import record_bytes
    rec = doc.record(eid, seq)
    assert rec is not None, f"specimen {eid} seq{seq} missing"
    return record_bytes(doc.seg[seq], rec, seq)


def _mine(enc, el, eid: int, seq: int) -> bytes:
    recs = {s: (c, o) for s, c, o in el.records(class_ids=enc.class_id_of)}
    cid, obj = recs[seq]
    body = enc.encode_object(cid, obj)
    stamp = zlib.adler32(struct.pack("<H", cid) + body) & 0xFFFFFFFF
    return enc.encode_record(seq, eid, stamp, cid, obj)


def _assert_exact(doc, enc, el, eid: int, seq: int = 102):
    mine = _mine(enc, el, eid, seq)
    orig = _original_record(doc, eid, seq)
    assert mine == orig, (f"{el.class_name} {eid} seq{seq}: constructed "
                          f"{len(mine)} B != original {len(orig)} B")


# ---------------------------------------------------------------------------
# 1. byte-exact reconstruction of real specimens (rstbasic)
# ---------------------------------------------------------------------------

@needs_corpus
def test_phase_byte_exact(doc, enc):
    _assert_exact(doc, enc, sk.new_phase(12589, "Existing"), 12589)
    _assert_exact(doc, enc, sk.new_phase(86961, "New Construction"), 86961)


@needs_corpus
def test_all_project_phases_byte_exact(doc, enc):
    ov = sk.default_phasing_overrides(materials=[105007, 105006, 8798, 29],
                                      line_patterns=[-1, 21, -3000010, 11],
                                      fill_patterns=[3, -1, 3, 4])
    el = sk.new_all_project_phases(1, [12589, 86961], phasing_overrides=ov)
    _assert_exact(doc, enc, el, 1, 102)
    _assert_exact(doc, enc, el, 1, 101)


@needs_corpus
def test_phase_filters_byte_exact(doc, enc):
    for eid, (name, dflt, pres) in zip([371, 372, 373, 374, 375],
                                         sk.DEFAULT_PHASE_FILTERS):
        _assert_exact(doc, enc, sk.new_phase_filter(eid, name, pres, dflt), eid)


@needs_corpus
def test_project_info_byte_exact(doc, enc):
    el = sk.new_project_info(49504, project_name="Sample House",
                             project_number="001-00", address="Enter address here",
                             client_name="Autodesk", project_status="Project Status",
                             issue_date="Issue Date")
    _assert_exact(doc, enc, el, 49504, 102)
    _assert_exact(doc, enc, sk.new_project_info(49504), 49504, 101)


@needs_corpus
def test_level_byte_exact(doc, enc):
    env = ((-51.66057056018548, -87.39567025725263),
           (66.52686260879011, 94.20488384847846))
    el = sk.new_level(311, "Level 1", 0.0, 305, extent_ft=env,
                      units_id=19236, geolocation_id=111428, flags=2074)
    # the specimen's plane axes carry floating-point drift; align them
    for pl in (el.obj["m_pSurface"], el.obj["m_pFace"]["value"]["m_pSurf"]):
        pl["value"]["m_xVec"] = [1.0, 6.3576025574306265e-15, -0.0]
        pl["value"]["m_yVec"] = [-0.0, 1.0, -0.0]
    _assert_exact(doc, enc, el, 311, 102)
    _assert_exact(doc, enc, el, 311, 101)
    _assert_exact(doc, enc, el, 311, 103)     # SerializedDummy rep


@needs_corpus
def test_level_type_byte_exact(doc, enc):
    el = sk.new_level_type(305, "8mm Head", line_category_id=306,
                           leader_category_id=309, font_id=308,
                           head_family_symbol_id=1417017, base_elevation=0,
                           room_computation_height_ft=3.9370078740157473)
    _assert_exact(doc, enc, el, 305, 102)


@needs_corpus
def test_view_types_byte_exact(doc, enc):
    _assert_exact(doc, enc, sk.new_view_type(49559, "3D View", "3d",
                                             poche_material_id=51455), 49559)
    _assert_exact(doc, enc, sk.new_view_type(69847, "Structural Plan",
                                             "structural_plan"), 69847)


@needs_corpus
def test_project_view_constellation_byte_exact(doc, enc):
    """The document's implicit project view (ancestral ids 230..233):
    its Viewer, DBDrawing and Viewport reconstruct byte-exact; the
    DBViewProject object itself differs only by the sample's link/browser
    edges (documented in the spec)."""
    pv = sk.new_project_view(sk.IdSource(230), phase_id=86961, phase_filter_id=375,
                             sun_settings_id=54520, invisible_style_id=201,
                             not_silhouette_style_id=55150)
    els = {e.elem_id: e for e in pv.elements()}
    _assert_exact(doc, enc, els[231], 231, 102)      # Viewer
    _assert_exact(doc, enc, els[231], 231, 101)
    _assert_exact(doc, enc, els[233], 233, 102)      # DBDrawing
    _assert_exact(doc, enc, els[232], 232, 102)      # Viewport
    _assert_exact(doc, enc, els[232], 232, 101)


@needs_corpus
def test_view_satellites_byte_exact(doc, enc):
    _assert_exact(doc, enc, sk.new_extent_elem(245444, 245443, (0.0, 0.0, -1.0)), 245444)
    _assert_exact(doc, enc, sk.new_extent_elem(245444, 245443, (0.0, 0.0, -1.0)), 245444, 101)
    sun = sk.new_sun_and_shadow_settings(245446, 245443, level_id=511122,
                                          annotation_id=245447, owner_regen=[111429])
    _assert_exact(doc, enc, sun, 245446)
    sp = sk.new_sketch_plane(245451, 245443, datum_id=245443,
                             elevation_ft=9.84251968503937, regen_level_id=245423)
    _assert_exact(doc, enc, sp, 245451)
    _assert_exact(doc, enc, sp, 245451, 101)
    _assert_exact(doc, enc, sk.new_light_scheme(1138906, 1138902), 1138906)
    _assert_exact(doc, enc, sk.new_model_clip_box(1138901, 1138900,
                                                  half_extent_ft=100.0), 1138901)


@needs_corpus
def test_site_elements_byte_exact(doc, enc):
    _assert_exact(doc, enc, sk.new_true_north(7850, 0.0, site_cut_material_id=519), 7850)
    gs = sk.new_geo_site(21747, "", shared_coord_guid="d9e0c609-1e18-4e32-85fe-a85e12e0f821")
    gs.obj["m_weatherStationName"] = "52939_2004"     # sample's stock station id
    _assert_exact(doc, enc, gs, 21747)
    _assert_exact(doc, enc, sk.new_geo_location(111428, 21747, "Project"), 111428, 101)
    bp = sk.new_base_point(111429, shared=True,
                           coord_ft=(-38.14983097953533, -11.422552423167835, -0.0),
                           geolocation_id=21748, tracking_id=113109)
    _assert_exact(doc, enc, bp, 111429)


@needs_corpus
def test_units_elem_byte_exact(doc, enc):
    """Feed the specimen's own 136 format entries through the constructor:
    the 36 KB UnitsElem reproduces byte-exact."""
    u = doc.value(19236)["m_units"]
    fmts = [(e["first"]["m_typeId"], e["second"]["m_unitTypeId"]["m_typeId"],
             e["second"]["m_symbolTypeId"]["m_typeId"] or None,
             e["second"]["m_accuracy"], e["second"]["m_bUseDefault"],
             e["second"]["m_bUseGrouping"], e["second"]["m_roundingMethod"])
            for e in u["m_formatOptionsMap"]]
    el = sk.new_units_elem(19236, [], universal_unit_system=u["m_universalUnitSystem"],
                           decimal_symbol=u["m_decimalSymbol"],
                           digit_grouping_symbol=u["m_digitGroupingSymbol"],
                           digit_grouping_amount=u["m_digitGroupingAmount"])
    el.obj["m_units"]["m_formatOptionsMap"] = [
        sk.format_options(a, b, c, d, use_default=e, use_grouping=f, rounding_method=g)
        for a, b, c, d, e, f, g in fmts]
    _assert_exact(doc, enc, el, 19236)
    assert len(u["m_formatOptionsMap"]) == 136


# ---------------------------------------------------------------------------
# 2. whole-skeleton schema validity (encode -> decode -> equal)
# ---------------------------------------------------------------------------

@needs_schema
def test_minimal_skeleton_roundtrip():
    skel = sk.build_minimal_skeleton(timestamp=0)
    rep = sk.roundtrip_report(skel.elements)
    assert rep["failed"] == 0, rep["failures"][:5]
    assert rep["records"] == 3 * len(skel.elements)
    # sensible composition
    kinds = {k: len(v) for k, v in skel.by_kind.items()}
    assert kinds["level"] == 2 and kinds["phase"] == 2 and kinds["view"] >= 3
    assert len(set(skel.element_ids())) == len(skel.elements)   # unique ids


@needs_schema
def test_view_constellation_cross_references():
    ids = sk.IdSource(1000)
    vt = sk.new_view_type(ids.next(), "3D View", "3d")
    v3 = sk.new_3d_view(ids, "{3D}", vt.elem_id, phase_id=-1, phase_filter_id=-1)
    view = v3.view
    by_cls = {e.class_name: e for e in v3.satellites}
    assert view.obj["m_viewerId"] == by_cls["Viewer3d"].elem_id
    assert view.obj["m_dbDrawingId"] == by_cls["DBDrawing"].elem_id
    assert view.obj["m_extentElemId"] == by_cls["ExtentElem"].elem_id
    assert view.obj["m_lightSchemeId"] == by_cls["LightSchemeElement"].elem_id
    assert view.obj["m_dbViewTypeId"] == vt.elem_id
    # the drawing lists the viewport; the viewport points back at the view
    vp = by_cls["Viewport"]
    assert by_cls["DBDrawing"].obj["m_viewports"] == [vp.elem_id]
    assert vp.obj["m_dbViewId"] == view.elem_id
    # sun link lives inside the ViewDisplayMgr
    sun = by_cls["SunAndShadowSettings"]
    assert view.obj["m_pViewDisplayMgr"]["value"]["m_lights"]["m_sunAndShadowSettingsId"] == sun.elem_id
    # satellites are owned by the view / their sub-owner
    assert by_cls["Viewer3d"].owner_id == view.elem_id
    assert by_cls["ModelClipBox"].owner_id == by_cls["Viewer3d"].elem_id
    assert vp.owner_id == by_cls["DBDrawing"].elem_id


@needs_schema
def test_plan_view_is_bound_to_its_level():
    ids = sk.IdSource(2000)
    lt = sk.new_level_type(ids.next())
    lv = sk.new_level(ids.next(), "L1", 0.0, lt.elem_id)
    vt = sk.new_view_type(ids.next(), "Floor Plan", "floor_plan")
    pv = sk.new_plan_view(ids, "L1", lv.elem_id, 0.0, vt.elem_id)
    obj = pv.view.obj
    assert obj["m_genElemId"] == lv.elem_id                     # the plan's level
    assert obj["m_viewDir"] == [0.0, 0.0, 1.0]                   # looking down
    assert obj["m_scale"] == 0.01                                # 1:100
    assert obj["m_cutPlaneElev"] == pytest.approx(3.937007874015748)  # 1200 mm cut
    sat = {e.class_name: e for e in pv.satellites}
    assert obj["m_fixedSketchPlaneId"] == sat["SketchPlane"].elem_id
    assert sat["SketchPlane"].obj["m_oPlaneRef"]["value"]["m_datumPlaneId"] == pv.view.elem_id
    assert obj["m_pPlanViewRange2"]["value"]["m_viewDepthPlaneLevelIds"][0] == lv.elem_id


def test_view_family_indices():
    assert sk.VIEW_FAMILY["3d"] == 102
    assert sk.VIEW_FAMILY["floor_plan"] == 109
    assert sk.VIEW_FAMILY["ceiling_plan"] == 111
    assert sk.VIEW_FAMILY["structural_plan"] == 120
    assert sk.PLAN_VIEW_DIRECTION["ceiling_plan"] == 1


def test_element_record_shape_without_schema():
    el = sk.new_phase(77, "Existing")
    recs = el.records(by_name=True)
    assert [r[0] for r in recs] == [101, 102, 103]
    assert recs[0][1] == "ElementHeader" and recs[1][1] == "ProjectPhase"
    assert recs[2][1] == "SerializedDummy" and recs[2][2] == {}
    row = el.elemrec_row(0)
    assert row == (77, 0, 0, 0, 77, sk.NO_OWNER, 0)
    # a view satellite carries its owner in the ElemRec
    vw = sk.new_viewer(78, 300)
    assert vw.elemrec_row(3)[5] == 300 and vw.elemrec_row(3)[1] == 3


# ---------------------------------------------------------------------------
# 3. the six minimal Global table streams
# ---------------------------------------------------------------------------

def test_minimal_globals_invariants():
    els = [sk.new_phase(10, "Existing"), sk.new_phase(11, "New")]
    gm = sk.minimal_globals(els, username="genesis", timestamp=1000,
                            document_guid="11111111-1111-1111-1111-111111111111",
                            episode_guid="22222222-2222-2222-2222-222222222222",
                            workset_guid="33333333-3333-3333-3333-333333333333")
    hist, dit, bfi = gm["History"], gm["DocumentIncrementTable"], gm["BasicFileInfo"]
    con, ws, et = gm["Contents"], gm["PartitionTable"], gm["ElemTable"]
    # History count == DIT records == BFI increments == 1
    assert len(hist["entries"]) == hist["hdr_count"] == 1
    assert len(dit["records"]) == 1 == int(bfi["unique_document_increments"])
    assert bfi["central_version_number"] == 1
    # DIT newest id_pair == (History count - 1, History count)
    assert tuple(dit["records"][-1]["id_pair"]) == (0, 1)
    # BFI GUID == History entry[0]
    assert bfi["unique_document_guid"] == hist["entries"][0][0] == bfi["central_episode_guid"]
    # Contents counters == DIT counters minus index 7; G equal; GUID == workset
    ctr = dit["records"][-1]["counters"]
    assert con["counters"] == ctr[:7] + ctr[8:]
    assert con["counter_g"] == dit["records"][-1]["counter_g"]
    assert con["creation_guid"] == ws["entries"][0]["guid"]
    # ElemTable count == elements, watermark == max id, sorted by id
    assert len(et["records"]) == 2
    assert et["footer"]["last_id"] == 11
    assert [r[4] for r in et["records"]] == [10, 11]
    # History format list ends at 2662 (Revit 2026)
    assert hist["format_versions"][-1] == 2662


def test_minimal_globals_encode_roundtrip():
    from rvt import stream_encoders as se
    els = [sk.new_phase(10, "Existing"), sk.new_project_info(11, project_name="G")]
    gm = sk.minimal_globals(els, username="genesis", timestamp=1000)
    enc = sk.encode_minimal_globals(gm)
    # each stream: encode -> decode -> encode reproduces the same bytes
    assert se.encode_elemtable(se.decode_elemtable(enc["ElemTable"])) == enc["ElemTable"]
    assert se.encode_history(se.decode_history(enc["History"])) == enc["History"]
    assert se.encode_increment_table(
        se.decode_increment_table(enc["DocumentIncrementTable"])) == enc["DocumentIncrementTable"]
    assert se.encode_partition_table(
        se.decode_partition_table(enc["PartitionTable"])) == enc["PartitionTable"]
    assert se.encode_contents(se.decode_contents(enc["Contents"])) == enc["Contents"]
    assert se.encode_basic_file_info(
        se.decode_basic_file_info(enc["BasicFileInfo"]),
        regenerate_mirror=True) == enc["BasicFileInfo"]
    assert len(enc["ContentsPrologue"]) == 24
    # ElemTable payload size: u16 tag + u32 count + 2 x 40-B rows + 24-B footer
    assert len(enc["ElemTable"]) == 6 + 2 * 40 + 24
    # our identity, never a template's
    bfi = se.decode_basic_file_info(enc["BasicFileInfo"])
    assert bfi["author"] == "rvt-writer" and bfi["format"] == "2026"
    assert bfi["last_save_path"] == "" and bfi["username"] == "genesis"


def test_globals_reject_duplicate_ids():
    els = [sk.new_phase(10, "A"), sk.new_phase(10, "B")]
    with pytest.raises(ValueError):
        sk.minimal_elemtable(els)


def test_id_source_and_alloc_compat():
    ids = sk.IdSource(50)
    assert ids.next() == 50 and ids.next_id() == 51 and ids.watermark == 51

    class Legacy:                       # e.g. rvt.mutate.Document
        def __init__(self):
            self.n = 7

        def next_id(self):
            self.n += 1
            return self.n

    assert sk._alloc(Legacy()) == 8
    assert sk._alloc(ids) == 52

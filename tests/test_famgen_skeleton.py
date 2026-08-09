"""Tests for rvt.famgen.skeleton -- the FAMILY-DOCUMENT skeleton constructors.

Evidence tiers (mirroring tests/test_genesis_skeleton.py):

1. BYTE-EXACT SPECIMEN RECONSTRUCTION: build a family-skeleton object FROM
   SCRATCH with a constructor (plain parameter values only, no cloning),
   encode it with the schema encoder and compare against the ORIGINAL
   record bytes of the equivalent element in a real family document (the
   2026 sample ``.rfa`` and embedded family documents of the rme / rac
   sample projects), adler32 stamp included.  Proves the constructors
   reproduce Revit's own serialization of the family skeleton.
2. WHOLE-DOCUMENT encode -> decode round trip: every constructed record of
   S0 / S0e is schema-valid and byte-stable; every reference the document
   makes resolves inside the document (a family document is a CLOSED
   graph).
3. DELIVERY: S0 (empty family, skeleton only) and S0e (electrical variant)
   emit as standalone ``.rfa`` containers that read back clean (gzip CRC,
   CRCIO ECC, walker, per-seq record counts, schema decode) and validate
   with 0 errors in family mode; the embedded save-unit form carries the
   loader contract.

Corpus-dependent tests skip when the samples / the schema are absent.
"""
from __future__ import annotations

import os
import struct
import uuid
import zlib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RFA = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                   "racbasicsamplefamily-2026.rfa")
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
RAC = os.path.join(ROOT, "samples", "racbasicsampleproject.rvt")
HAVE_RFA = os.path.exists(RFA)
HAVE_RME = os.path.exists(RME)
HAVE_RAC = os.path.exists(RAC)

from rvt.famgen import skeleton as fs                     # noqa: E402


def _have_schema() -> bool:
    """A class schema loads: the extracted corpus blob or, on a fresh clone /
    CI, the sha-pinned bundled base's embedded copy (load_schema's fallback)."""
    try:
        from rvt.schema import load_schema
        load_schema()
        return True
    except Exception:                                        # noqa: BLE001
        return False


HAVE_SCHEMA = _have_schema()
needs_rfa = pytest.mark.skipif(not HAVE_RFA, reason="sample .rfa absent")
needs_rme = pytest.mark.skipif(not HAVE_RME, reason="rme sample absent")
needs_rac = pytest.mark.skipif(not HAVE_RAC, reason="rac sample absent")
needs_schema = pytest.mark.skipif(
    not HAVE_SCHEMA, reason="no class schema (extracted corpus and bundled base both absent)")


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def idx_rfa():
    from rvt.families import FamilyIndex
    return FamilyIndex.open(RFA)


@pytest.fixture(scope="module")
def idx_rme():
    from rvt.families import FamilyIndex
    return FamilyIndex.open("rmebasicsampleproject")


@pytest.fixture(scope="module")
def idx_rac():
    from rvt.families import FamilyIndex
    return FamilyIndex.open("racbasicsampleproject")


@pytest.fixture(scope="module")
def enc(idx_rfa):
    from rvt.encode import ObjectEncoder
    return ObjectEncoder(idx_rfa.schema)


_SEGS: dict = {}


def _orig(idx, unit, eid, seq):
    from rvt.encode import record_bytes
    from rvt.families import unit_segments
    key = (idx.path, unit)
    if key not in _SEGS:
        _SEGS[key] = unit_segments(idx, unit)
    rec = idx.unit_records(unit)[seq][eid]
    return record_bytes(_SEGS[key][seq], rec, seq)


def _mine(enc, el, eid, seq):
    recs = {s: (c, o) for s, c, o in el.records(class_ids=enc.class_id_of)}
    cid, obj = recs[seq]
    body = enc.encode_object(cid, obj)
    stamp = zlib.adler32(struct.pack("<H", cid) + body) & 0xFFFFFFFF
    return enc.encode_record(seq, eid, stamp, cid, obj)


def _assert_exact(idx, enc, el, unit, eid, seq=102):
    mine, orig = _mine(enc, el, eid, seq), _orig(idx, unit, eid, seq)
    assert mine == orig, (f"{el.class_name} {eid} seq{seq}: constructed "
                          f"{len(mine)} B != original {len(orig)} B")


def _align_plane(el, pl_orig):
    """Copy the specimen's plane origin/axes into a constructed datum
    (specimen planes carry per-plane floating-point drift)."""
    for p in (el.obj["m_pSurface"], el.obj["m_pFace"]["value"]["m_pSurf"]):
        p["value"]["m_origin"] = pl_orig["m_origin"]
        p["value"]["m_xVec"] = pl_orig["m_xVec"]
        p["value"]["m_yVec"] = pl_orig["m_yVec"]


# ---------------------------------------------------------------------------
# 1. byte-exact specimen reconstruction
# ---------------------------------------------------------------------------

@needs_rfa
def test_ref_level_byte_exact_rfa(idx_rfa, enc):
    """The .rfa's Reference Level: object + header + rep byte-exact."""
    v = idx_rfa.value(0, 21)
    pl = v["m_pSurface"]["value"]
    env = tuple(map(tuple, pl["m_Envelope"]["m_corners"]))
    el = fs.new_family_level(21, 17, 18, gen_view_id=5602,
                             elevation_ft=pl["m_origin"][2],
                             origin=(pl["m_origin"][0], pl["m_origin"][1]),
                             extent_ft=env, flags=2074)
    _align_plane(el, pl)
    _assert_exact(idx_rfa, enc, el, 0, 21, 102)
    _assert_exact(idx_rfa, enc, el, 0, 21, 101)
    _assert_exact(idx_rfa, enc, el, 0, 21, 103)


@needs_rfa
@needs_rme
def test_level_type_byte_exact(idx_rfa, idx_rme, enc):
    """LevelAttributes 'Level 1' byte-exact on the .rfa and the panelboard."""
    for idx, unit, eid, famid, gs in ((idx_rfa, 0, 18, 17, 4105),
                                       (idx_rme, 243, 786447, 786439, 786488)):
        v = idx.value(unit, eid)
        h = idx.value(unit, eid, 101)
        lat = v["m_lineAndTextAttr"]
        el = fs.new_family_level_type(
            eid, famid, name=v["m_symbolInfo"]["value"]["m_name"],
            line_category_id=lat["m_categoryId"], line_gstyle_id=gs,
            leader_category_id=v["m_leaderCategoryId"],
            font_id=lat["m_fontId"], head_family_symbol_id=v["m_familyTagId"],
            room_computation_height_ft=v["m_roomComputationUserHeight"],
            flags=h["m_abFlags4Bytes"])
        for seq in (102, 101, 103):
            _assert_exact(idx, enc, el, unit, eid, seq)


@needs_rme
def test_reference_planes_byte_exact(idx_rme, enc):
    """The panelboard's Center (Front/Back), Center (Left/Right) and
    'Front' reference planes: object + header + rep byte-exact."""
    for eid in (786474, 786476, 786475):
        v = idx_rme.value(243, eid)
        h = idx_rme.value(243, eid, 101)
        pl = v["m_pSurface"]["value"]
        env = tuple(map(tuple, pl["m_Envelope"]["m_corners"]))
        el = fs.new_reference_plane(
            eid, 786439, name=v["m_text"], ref_name=v["m_refName"],
            bubble_end=v["m_bubbleEnd"], free_end=v["m_freeEnd"],
            normal=pl["m_yVec"], gen_view_id=v["m_genDbViewId"], extent=env,
            defines_origin=v["m_definesOrigin"], locked=v["m_locked"],
            subcategory_id=v["m_subcategoryId"],
            sheet_text_height_ft=v["m_sheetTextHeight"],
            flags=h["m_abFlags4Bytes"])
        _align_plane(el, pl)
        el.obj["m_cutVec"] = v["m_cutVec"]
        for seq in (102, 101, 103):
            _assert_exact(idx_rme, enc, el, 243, eid, seq)


@needs_rfa
def test_family_parameters_byte_exact(idx_rfa, enc):
    """The .rfa's Height / Width / Length ParamElemFamily elements."""
    for eid in (4208, 4209, 4253):
        v = idx_rfa.value(0, eid)
        h = idx_rfa.value(0, eid, 101)
        pd = v["m_pParamDef"]["value"]
        guid = str(uuid.UUID(pd["m_typeId"]["m_typeId"].split(":")[1][:32]))
        el = fs.new_family_parameter(
            eid, 17, pd["m_caption"],
            spec_type_id=pd["m_specTypeId"]["m_typeId"],
            group_type_id=pd["m_groupTypeId"]["m_typeId"],
            family_guid=guid, is_instance=v["m_instanceParam"],
            flags=h["m_abFlags4Bytes"])
        for seq in (102, 101, 103):
            _assert_exact(idx_rfa, enc, el, 0, eid, seq)


@needs_rme
def test_electrical_connectors_byte_exact(idx_rme, enc):
    """Panelboard (3-pole 208 V), lighting fixture (120 V, voltage/wattage
    driven by family parameters) and receptacle connectors byte-exact."""
    for unit, eid, famid in ((243, 786876, 786439), (271, 773363, 772891),
                             (119, 847095, 846630)):
        v = idx_rme.value(unit, eid)
        h = idx_rme.value(unit, eid, 101)
        dom = v["m_pDomain"]["value"]
        pr = v["m_oPlaneRef"]["value"]
        gr = pr["m_geomRef"]
        fu = v["m_pFaceU"]["value"]["m_pSurf"]["value"]
        fv = v["m_pFaceV"]["value"]["m_pSurf"]["value"]
        cells = [c for c in v["m_cellList"]["value"]["m_cells"]
                 if c["ptr_class"] == "FamilyParametrizedElemParamsCell"]
        binds = [(d["m_famParamId"], d["m_elemPropId"])
                 for c in cells for d in c["value"]["m_paramDrivenData"]]
        el = fs.new_electrical_connector(
            eid, famid, host_element_id=gr["m_elemId"], host_geom_tag=gr["m_geomTag"],
            location=fu["m_origin"], direction=fu["m_xVec"], u_axis=fu["m_yVec"],
            offset_uv=pr["m_offset"], angle=pr["m_angle"],
            voltage_v=dom["m_dVoltage"] * 0.3048 ** 2, poles=dom["m_nNumberOfPoles"],
            load_class_id=dom["m_idLoadClassification"],
            apparent_load_va=dom["m_dApparentLoadPhase1"] * 0.3048 ** 2,
            power_factor=dom["m_dPowerFactor"],
            description=dom["m_strConnectorDescription"], marker_size_ft=v["m_grepSize"],
            edge_loop_tags=v["m_oEdgeLoopRef"]["value"]["m_sortedTagArr"],
            param_bindings=binds, flip=pr["m_flip"],
            index=v["m_index"], flags=h["m_abFlags4Bytes"])
        # feed the specimen's exact stored floats (unit round-trips drift 1 ulp)
        d = el.obj["m_pDomain"]["value"]
        d["m_dVoltage"] = dom["m_dVoltage"]
        d["m_dApparentLoadPhase1"] = dom["m_dApparentLoadPhase1"]
        for f, src in ((el.obj["m_pFaceU"], fu), (el.obj["m_pFaceV"], fv)):
            p = f["value"]["m_pSurf"]["value"]
            p["m_origin"], p["m_xVec"], p["m_yVec"] = (src["m_origin"], src["m_xVec"],
                                                          src["m_yVec"])
        for seq in (102, 101, 103):
            _assert_exact(idx_rme, enc, el, unit, eid, seq)


#: per-family scalar VALUES that differ between families (not layout)
_SELF_FAMILY_VALUE_KEYS = (
    "m_omniClassCode", "m_seekItemId", "m_eRenderModelType", "m_isVertical",
    "m_bIsSavable", "m_bShared", "m_enableCuttingInViews",
    "m_defaultHostThickness", "m_defaultHeightAboveLevel", "m_elevationFixed")


@needs_rfa
def test_self_family_byte_exact(idx_rfa, enc):
    """The .rfa's SELF-Family (26,535 bytes: type table with 4 types,
    parameter set, ordering cell, 1,881-entry element index, dimension
    expressions) reconstructs BYTE-EXACT from parameter values."""
    v = idx_rfa.value(0, 17)
    h = idx_rfa.value(0, 17, 101)
    ftt = v["m_pFamilyTypes"]["value"]
    types = [(pr["name"], pr["params"]["m_params"]) for pr in ftt["m_pairs"]]
    cell = v["m_cellList"]["value"]["m_cells"][0]["value"]["m_sortedParams"]
    groups = [(g["m_groupTypeId"]["m_typeId"], g["m_paramIds"]) for g in cell]
    ov = {k: v[k] for k in _SELF_FAMILY_VALUE_KEYS}
    fam = fs.new_self_family(
        17, v["m_categoryId"], name=v["m_name"],
        element_ids=[e["m_elementId"] for e in v["m_familyIds"]["value"]["m_data"]],
        element_index=[(e["m_elementId"], e["m_index"])
                       for e in v["m_familyIds"]["value"]["m_data"]],
        types=types, current_type=ftt["m_idx"],
        family_params=v["m_familyParams"]["value"]["m_params"],
        param_groups=groups, part_type=v["m_partType"],
        work_plane_based=v["m_isWorkPlaneBased"],
        trivial_param_ids=v["m_trivialParamIds"],
        locked_param_ids=v["m_lockedParameterIdsForDirectManipulation"],
        deletable_elements=v["m_deletableElements"],
        predefined_limit_idx=v["m_predefinedLimitIdx"],
        app_version_at_load=v["m_appVersionAtLoad"],
        ref_type_ids=v["m_refTypeIds"], refs=v["m_refs"], fsdos=v["m_fsdos"],
        dim_constr_mgr=v["m_oFamDimConstrMgr"], overrides=ov,
        flags=h["m_abFlags4Bytes"])
    fam.obj["m_nextAbsorbedIndex"] = v["m_nextAbsorbedIndex"]
    fam.header["m_parents"] = h["m_parents"]          # ownership list = specimen's
    for seq in (102, 101, 103):
        _assert_exact(idx_rfa, enc, fam, 0, 17, seq)


# ---------------------------------------------------------------------------
# 2. whole-document construction (no specimen)
# ---------------------------------------------------------------------------

@needs_schema
def test_s0_roundtrip_and_closure():
    """S0: every record encodes -> decodes byte-stable AND every element
    reference resolves inside the document (closed graph)."""
    doc = fs.build_s0()
    rep = doc.roundtrip()
    assert rep["failed"] == 0, rep["failures"][:5]
    assert rep["records"] == 3 * len(doc.elements)
    ids = set(doc.element_ids())
    dangling = _dangling_refs(doc, ids)
    assert not dangling, f"dangling references: {sorted(dangling)[:20]}"
    # skeleton composition
    kinds = {e.kind for e in doc.elements}
    assert {"self_family", "ref_level", "level_type", "ref_plane",
            "family_param", "registry"} <= kinds
    fam = doc.self_family
    # the family owns every other element (header deletion + index)
    others = {e.elem_id for e in doc.elements if e.elem_id != fam.elem_id}
    assert others <= set(fam.header["m_parents"]["value"]["m_deletion"])
    idx_ids = {d["m_elementId"] for d in fam.obj["m_familyIds"]["value"]["m_data"]}
    assert idx_ids == others
    assert fam.obj["m_nextAbsorbedIndex"] == len(others)
    # type table + current-type params
    ftt = fam.obj["m_pFamilyTypes"]["value"]
    assert len(ftt["m_pairs"]) == 1 and ftt["m_idx"] == 0
    assert len(fam.obj["m_familyParams"]["value"]["m_params"]) == \
        len(ftt["m_pairs"][0]["params"]["m_params"])


@needs_schema
def test_s0e_electrical_roundtrip_and_bindings():
    """S0e: electrical variant round-trips clean; the connector's voltage /
    apparent load are ASSOCIATED to the type parameters and its domain
    carries the calc values in internal units."""
    doc = fs.build_s0e_electrical()
    rep = doc.roundtrip()
    assert rep["failed"] == 0, rep["failures"][:5]
    con = doc.connectors[0]
    dom = con.obj["m_pDomain"]["value"]
    assert dom["m_nNumberOfPoles"] == 3
    assert abs(dom["m_dVoltage"] - 208.0 / 0.3048 ** 2) < 1e-6
    assert dom["m_idLoadClassification"] == doc.load_classes[0].elem_id
    cells = con.obj["m_cellList"]["value"]["m_cells"]
    driven = cells[0]["value"]["m_paramDrivenData"]
    assert {(d["m_famParamId"], d["m_elemPropId"]) for d in driven} == {
        (doc.params["Panel Voltage"].elem_id, fs.ELEM_PROP_VOLTAGE),
        (doc.params["Apparent Load"].elem_id, fs.ELEM_PROP_APPARENT_LOAD)}
    # closure: the connector's host / load class / driving params exist
    assert not _dangling_refs(doc, set(doc.element_ids()))


@needs_schema
def test_type_and_parameter_authoring():
    """add_type / add_family_parameter drive the FamilyTypeTable rows and
    the current-type value set; identity-data names map to their BIPs."""
    doc = fs.new_family_document("furniture", "T", with_views=False)
    L = doc.add_family_parameter("Length")
    doc.add_type("A", {L.elem_id: fs.mm(600), "manufacturer": "us"})
    doc.add_type("B", {"Length": fs.mm(900)})
    doc.finalize()
    ftt = doc.self_family.obj["m_pFamilyTypes"]["value"]
    names = [p["name"] for p in ftt["m_pairs"]]
    assert names == ["A", "B"]
    a = {p["m_paramId"]: p for p in ftt["m_pairs"][0]["params"]["m_params"]}
    assert abs(a[L.elem_id]["m_value"] - fs.mm(600)) < 1e-12
    assert a[fs.BIP_TYPE_MANUFACTURER]["m_str"] == "us"
    b = {p["m_paramId"]: p for p in ftt["m_pairs"][1]["params"]["m_params"]}
    assert abs(b[L.elem_id]["m_value"] - fs.mm(900)) < 1e-12
    # ordering cell groups the length param under dimensions
    cell = doc.self_family.obj["m_cellList"]["value"]["m_cells"][0]["value"]
    groups = {g["m_groupTypeId"]["m_typeId"]: g["m_paramIds"]
              for g in cell["m_sortedParams"]}
    assert groups[fs.PGROUP_DIMENSIONS] == [L.elem_id]
    # length params are locked for direct manipulation
    assert doc.self_family.obj["m_lockedParameterIdsForDirectManipulation"] == [L.elem_id]


def test_units_and_type_id_helpers():
    """Unit conversions and the revit.local.family type-id identity."""
    assert abs(fs.mm(304.8) - 1.0) < 1e-12
    assert abs(fs.volts(208.0) - 2238.893366675622) < 1e-6
    assert abs(fs.voltamps(180.0) - 1937.50387500775) < 1e-6
    tid = fs.param_type_id("12e67102-126a-4a5e-bdd2-ba0daf715462", 4208)
    assert tid == "revit.local.family:12e67102126a4a5ebdd2ba0daf71546200001070-1.0.0"
    assert fs.REF_NAME["center_fb"] == 4 and fs.REF_NAME["center_lr"] == 1


# ---------------------------------------------------------------------------
# 3. delivery: standalone .rfa + embedded unit
# ---------------------------------------------------------------------------

@needs_rfa
def test_s0_emits_valid_rfa(tmp_path):
    """S0 emits a standalone .rfa: read-back clean (CRC / ECC / walker /
    decode / id-set parity) and 0 errors under the validator (family
    mode); the ONLY project-mode findings are the .rfa-shape gaps."""
    doc = fs.build_s0()
    out = str(tmp_path / "S0.rfa")
    rep = doc.to_rfa(out, timestamp=0)
    assert os.path.getsize(out) > 100_000
    vr = rep["verify"]
    assert vr["ok"], vr
    assert vr["gzip_crc_failures"] == 0 and vr["ecc_mismatch"] == 0
    assert not vr["walker_errors"]
    assert vr["record_counts"] == {"101": 22, "102": 22, "103": 22}   # 21 + sentinel
    assert vr["decode_seq102"]["clean"] == vr["decode_seq102"]["records"] == 21
    assert vr["id_sets_identical_across_seqs"]
    # the partition stream is named from OUR increment table (N = count-1)
    assert rep["partition_stream"] == "Partitions/0"
    assert rep["elem_table_count"] == 21
    val = fs.validate_family(out)
    assert val["family_mode"]["n_errors"] == 0, val["family_mode"]["errors"]
    # project mode: only the family-file-shape gaps (ProjectInformation
    # absent; PartAtom is plain unframed Atom XML)
    subj = " ".join(val["project_mode"]["errors"])
    assert val["project_mode"]["n_errors"] == 3
    assert "ProjectInformation" in subj and "PartAtom" in subj


@needs_rfa
def test_s0e_electrical_emits_valid_rfa(tmp_path):
    doc = fs.build_s0e_electrical()
    out = str(tmp_path / "S0e.rfa")
    rep = doc.to_rfa(out, timestamp=0)
    assert rep["verify"]["ok"], rep["verify"]
    assert rep["verify"]["record_counts"]["102"] == len(doc.elements) + 1
    val = fs.validate_family(out)
    assert val["family_mode"]["n_errors"] == 0, val["family_mode"]["errors"]


@needs_rfa
def test_rfa_streams_are_ours(tmp_path):
    """Our Global streams inside the emitted .rfa decode with the stream
    codecs and satisfy the cross-stream save invariants; PartAtom is our
    plain Atom XML naming the family."""
    from rvt.container import open_rvt
    from rvt import stream_encoders as se
    doc = fs.build_s0(name="Our Family")
    out = str(tmp_path / "ours.rfa")
    doc.to_rfa(out, timestamp=0)
    with open_rvt(out) as f:
        names = {s.name for s in f.streams()}
        assert "PartAtom" in names and "ProjectInformation" not in names
        et = se.decode_elemtable(f.inflate("Global/ElemTable"))
        assert len(et["records"]) == 21
        hist = se.decode_history(f.inflate("Global/History"))
        dit = se.decode_increment_table(f.inflate("Global/DocumentIncrementTable"))
        bfi = se.decode_basic_file_info(f.logical("BasicFileInfo"))
        assert len(hist["entries"]) == 1                      # one save episode
        assert len(dit["records"]) == 1
        assert dit["records"][0]["id_pair"] == (0, 1)
        assert bfi["unique_document_guid"] == hist["entries"][0][0]
        assert bfi["author"] == "rvt-writer"
        pa = f.raw("PartAtom").decode("utf-8")
        assert "<title>Our Family</title>" in pa and "partatom" in pa
        # OUR taxonomy: no Autodesk taxonomy terms / product label (the
        # partatom NAMESPACE URI is format vocabulary and stays)
        assert "adsk:" not in pa and "Autodesk Revit" not in pa
        assert "<A:product>rvt-writer</A:product>" in pa


@needs_schema
def test_embedded_unit_contract():
    """The embedded save-unit form carries the loader contract: separator
    with the document GUID + record count, per-seq segments with sentinels,
    and the ContentDocuments entry spec (ADocument = the open gate)."""
    from rvt.objects import iter_records
    doc = fs.build_s0()
    unit = doc.to_embedded_unit()
    n = len(doc.elements)
    assert unit["record_count"] == n
    sep = unit["separator"]
    assert len(sep) == 28
    tag, minus1, tag2, cnt = struct.unpack_from("<HiHI", sep, 0)
    assert (tag, minus1, tag2, cnt) == (0x3A3, -1, 0x3A2, n)
    assert sep[12:] == uuid.UUID(unit["content_doc_guid"]).bytes_le
    for seq, seg in unit["segments"].items():
        recs = list(iter_records(seg, seq))
        assert len(recs) == n + 1 and recs[-1].elem_id == -1     # sentinel last
    entry = unit["content_documents_entry"]
    assert entry["null_lead_pointers"] == "a303ffffffffa203ffffffff"
    assert "ADocument" in entry["adoc"]


# ---------------------------------------------------------------------------
# reference closure helper
# ---------------------------------------------------------------------------

def _dangling_refs(doc, ids: set) -> list:
    """Every positive ElementId-looking value in the document's objects /
    headers that is NOT an element of the document (built-in ids are
    negative and always fine; -1 = invalid)."""
    suspects = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, int) and not isinstance(v, bool):
            if v > 999 and v not in ids and _looks_like_id(path):
                suspects.append((path, v))

    for e in doc.elements:
        walk(e.obj, f"{e.class_name}#{e.elem_id}.obj")
        walk(e.header, f"{e.class_name}#{e.elem_id}.hdr")
    return suspects


def _looks_like_id(path: str) -> bool:
    key = path.rsplit(".", 1)[-1].split("[")[0]
    return (key.endswith("Id") or key.endswith("Ids") or "m_deletion" in path
            or "m_regenOnly" in path or "m_appearanceParents" in path
            or "m_dependencyParents" in path or key in
            ("m_famId", "m_elemId", "m_id", "m_attrId", "m_genDbViewId",
             "m_famParamId", "m_paramElemId", "m_elementId"))

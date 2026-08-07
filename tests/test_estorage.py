"""Extensible Storage (ES) -- the last decode gap: schema catalog + entity blobs.

Proves, on the real corpus:
  * the in-model schema catalog (``ESSchemaStorage.m_schemaUsageMap`` in
    ``Global/Latest``) is located + decoded, and the GUID-free structural
    locator finds the same map without any entity-token seeds;
  * entity blobs decode to structured values and re-encode BYTE-EXACT, both
    as pure blobs (:func:`decode_entity_blob`) and inside whole element
    records (:class:`ESDecoder`/:class:`ESEncoder` -> record bytes identical);
  * the corpus reaches 0 undecodable ES elements (rme 1,171 / rstbasic 7 /
    dach 1,743 -- dach is ``slow``, skip with RVT_SKIP_LARGE=1);
  * the manipulate byte-exact precondition now passes for an ES element, and
    an ES field value can be edited through the ordinary JSON-path modify.
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
RAC = os.path.join(ROOT, "samples", "racbasicsampleproject.rvt")
DACH = os.path.join(ROOT, "samples", "dach-sample-project.rvt")


def _need(path):
    if not os.path.exists(path):
        pytest.skip(f"sample not present: {path}")


@pytest.fixture(scope="module")
def rst_doc():
    _need(RST)
    from rvt.mutate import Document
    return Document.from_file(RST)


@pytest.fixture(scope="module")
def rme_doc():
    _need(RME)
    from rvt.mutate import Document
    return Document.from_file(RME)


@pytest.fixture(scope="module")
def rst_cat(rst_doc):
    from rvt import estorage
    return estorage.schemas(rst_doc)


@pytest.fixture(scope="module")
def rme_cat(rme_doc):
    from rvt import estorage
    return estorage.schemas(rme_doc)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_parse_type_vocabulary():
    from rvt.estorage import parse_type, ESSchemaError
    assert parse_type("int") == ("prim", "<i")
    assert parse_type("double") == ("prim", "<d")
    assert parse_type("bool") == ("bool",)
    assert parse_type("TCHAR") == ("string",)
    assert parse_type("AStringWrapper") == ("string",)
    assert parse_type("GUIDvalue") == ("guid",)
    assert parse_type("ElementId") == ("elementid",)
    assert parse_type("XYZ") == ("xyz",)
    assert parse_type("ESEntity") == ("entity",)
    assert parse_type("std::pair< AString, ESEntity >") == \
        ("pair", ("string",), ("entity",))
    assert parse_type("std::pair< int, ElementId >") == \
        ("pair", ("prim", "<i"), ("elementid",))
    with pytest.raises(ESSchemaError):
        parse_type("SomeUnknownType")


def test_guid_string_bytes_roundtrip():
    from rvt.estorage import guid_str, guid_bytes
    raw = bytes.fromhex("14232a761c1d8740a58fbab902f57be5")
    g = guid_str(raw)
    assert g == "762a2314-1d1c-4087-a58f-bab902f57be5"
    assert guid_bytes(g) == raw


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------

def test_catalog_rstbasic(rst_cat):
    cat = rst_cat
    assert len(cat) == 2 and cat.map_count == 2
    names = {s.name: s for s in cat}
    assert set(names) == {"AREXContentGenerator", "DaylightingAnalysisInfo"}
    day = names["DaylightingAnalysisInfo"]
    assert day.vendor_id == "ADSK"
    assert day.guid == "5d9588ee-e6c7-4c96-87dc-df2a5fbe6613"
    # fields come out in entryIndex (serialization) order
    assert [(f.name, f.type_name, f.entry_index) for f in day.fields] == [
        ("AnalysisId", "TCHAR", 0), ("ResultsInvalid", "int", 1)]
    # Autodesk's EStorageTracking registry: schema guid -> element ids
    assert cat.tracking["4c817959-0028-4a83-b3e7-cd1e832a459a"] == [
        1372292, 1372482, 1375817, 1376990, 1377250, 1377640]
    assert cat.tracking[day.guid] == [1382860]


def test_catalog_rme(rme_cat):
    cat = rme_cat
    assert len(cat) == 2 and cat.map_offset == 0x327610
    duct = cat.get("762a2314-1d1c-4087-a58f-bab902f57be5")
    pipe = cat.get("1b022a2b-5722-4787-928a-4f29ca9d8811")
    assert duct.name == pipe.name == "CoefficientFromTable"
    assert duct.vendor_id == "ADSK" and duct.documentation == "Version1"
    assert [f.name for f in duct.fields] == ["ASHRAETableName"]
    assert [f.name for f in pipe.fields] == ["PipeFittingKFactorTableName"]
    assert duct.fields[0].type_name == "TCHAR"
    assert duct.used_in_host and pipe.used_in_host
    assert len(cat.tracking[duct.guid]) == 657
    assert len(cat.tracking[pipe.guid]) == 514
    assert cat.tracking[duct.guid][:3] == [392203, 393086, 393092]


def test_catalog_guid_free_locator_agrees(rme_doc, rme_cat):
    """The GUID-free structural scan finds the same map with no seeds."""
    from rvt import estorage
    from rvt.objects import ObjectDecoder
    gl, _ = estorage._global_latest_bytes(rme_doc)
    dec = ObjectDecoder(rme_doc.dec.schema)
    off, count, entries = estorage.locate_schema_map(gl, dec, seed_guids=None)
    assert off == 0x327610 and count == 2 and len(entries) == 2
    assert sorted(entries) == sorted(s.offset for s in rme_cat)


def test_entity_free_project_has_empty_catalog():
    """racbasic registers no ES schemas: empty catalog, nothing to decode."""
    _need(RAC)
    from rvt.mutate import Document
    from rvt import estorage
    doc = Document.from_file(RAC)
    cat = estorage.schemas(doc)
    assert len(cat) == 0
    res = estorage.verify_document(doc, cat)
    assert res.records_examined == 0 and res.entities == 0


# ---------------------------------------------------------------------------
# blob-level codec (pure functions)
# ---------------------------------------------------------------------------

def test_blob_roundtrip_rstbasic(rst_doc, rst_cat):
    from rvt import estorage
    closures = estorage.collect_entity_closures(rst_doc, rst_cat)
    assert len(closures) == 7          # 6 RebarShape + 1 DataStorage
    for c in closures:
        ent = estorage.decode_entity_blob(c["blob"], rst_cat, c["schema_guid"])
        assert ent["errors"] == [] and ent["consumed"] == ent["total"], c["elem_id"]
        assert estorage.encode_entity_blob(ent, rst_cat) == c["blob"], c["elem_id"]
    ds = next(c for c in closures if c["class"] == "DataStorage")
    ent = estorage.decode_entity_blob(ds["blob"], rst_cat, ds["schema_guid"])
    assert ent["schema"] == "DaylightingAnalysisInfo"
    assert ent["fields"] == {"AnalysisId": "", "ResultsInvalid": 0}
    assert ds["blob"] == b"\x00" * 8      # empty AString + int 0
    rebar = next(c for c in closures if c["class"] == "RebarShape")
    ent = estorage.decode_entity_blob(rebar["blob"], rst_cat, rebar["schema_guid"])
    ident = ent["fields"]["Identity"]
    assert isinstance(ident, str) and len(ident) == 64   # base64 identity string


def test_blob_roundtrip_rme(rme_doc, rme_cat):
    from rvt import estorage
    closures = estorage.collect_entity_closures(rme_doc, rme_cat, limit=200)
    assert len(closures) == 200
    for c in closures:
        ent = estorage.decode_entity_blob(c["blob"], rme_cat, c["schema_guid"])
        assert ent["errors"] == [] and ent["consumed"] == ent["total"]
        assert estorage.encode_entity_blob(ent, rme_cat) == c["blob"]
    first = closures[0]
    ent = estorage.decode_entity_blob(first["blob"], rme_cat, first["schema_guid"])
    key = "ASHRAETableName" if ent["schema_guid"].startswith("762a2314") \
        else "PipeFittingKFactorTableName"
    assert isinstance(ent["fields"][key], str) and ent["fields"][key]


# ---------------------------------------------------------------------------
# record-level: whole records decode 100 % and re-encode byte-exact
# ---------------------------------------------------------------------------

def test_es_decoder_closes_the_gap(rme_doc, rme_cat):
    """The base decoder fails at m_blob ('unknown class 0x2314' = the schema
    GUID's low bytes); ESDecoder decodes the whole record clean."""
    from rvt import estorage
    from rvt.objects import ObjectDecoder
    r = rme_doc.record(392203, 102)
    base = ObjectDecoder(rme_doc.dec.schema).decode_record(r.class_id, r.payload)
    assert not base.clean
    assert "unknown class 0x2314" in base.errors[0]["error"]
    assert base.errors[0]["field"].endswith("ESEntityCell.m_entityMap[0].second.m_blob")
    dec = estorage.ESDecoder(rme_doc.dec.schema, rme_cat)
    o = dec.decode_record(r.class_id, r.payload)
    assert o.clean and o.errors == [] and o.consumed == o.total
    ents = estorage.entities_in(o.value)
    assert len(ents) == 1
    assert ents[0]["schema"] == "CoefficientFromTable"
    assert ents[0]["fields"] == {"ASHRAETableName": "SR3-1"}
    # symmetric encoder reproduces the record payload
    enc = estorage.ESEncoder(dec)
    assert enc.encode_object(r.class_id, o.value) == r.payload


def test_record_roundtrip_rstbasic(rst_doc, rst_cat):
    from rvt import estorage
    res = estorage.verify_document(rst_doc, rst_cat)
    assert res.records_examined == 7
    assert res.decode_clean == 7 and res.undecodable == 0
    assert res.roundtrip_exact == 7
    assert res.by_class == {"RebarShape": 6, "DataStorage": 1}


def test_record_roundtrip_rme(rme_doc, rme_cat):
    from rvt import estorage
    res = estorage.verify_document(rme_doc, rme_cat)
    assert res.records_examined == 1171
    assert res.decode_clean == 1171 and res.undecodable == 0
    assert res.roundtrip_exact == 1171
    assert res.entities == 1171 and res.by_class == {"FamilyInstance": 1171}
    # entity counts per schema == Autodesk's own tracking table
    assert res.by_schema == {g: len(ids) for g, ids in rme_cat.tracking.items()}


def test_es_report_rme(rme_doc, rme_cat):
    from rvt import estorage
    rep = estorage.es_report(rme_doc, rme_cat)
    assert rep["schema_count"] == 2
    by = {s["guid"]: s for s in rep["schemas"]}
    assert len(by["762a2314-1d1c-4087-a58f-bab902f57be5"]["element_ids"]) == 657
    assert len(by["1b022a2b-5722-4787-928a-4f29ca9d8811"]["element_ids"]) == 514
    assert by["762a2314-1d1c-4087-a58f-bab902f57be5"]["element_ids"][0] == 392203


# ---------------------------------------------------------------------------
# manipulate integration: ES elements become MODIFIABLE
# ---------------------------------------------------------------------------

def test_manipulate_precondition_passes_and_es_field_is_editable(rme_doc, rme_cat):
    """With the ES decoder/encoder in place, the un-editable rme fittings
    pass the byte-exact edit precondition and their ES value is editable."""
    from rvt import estorage, manipulate
    from rvt.mutate import Document
    doc = Document.from_file(RME)
    doc.dec = estorage.ESDecoder(doc.dec.schema, rme_cat)     # <- the integration
    sess = manipulate.session(doc)
    sess.enc = estorage.ESEncoder(doc.dec)                    # <- mirrored encoder
    eid = 392203
    # precondition (_orig_bytes_check) runs inside value(); it used to REFUSE
    v = sess.value(eid, 102)
    path = ("m_cellList.value.m_cells[0].value.m_entityMap[0]"
            ".second.m_blob.fields.ASHRAETableName")
    assert manipulate.get_path(v, path) == "SR3-1"
    plan = manipulate.modify_element(doc, eid, {path: "SR3-2"})
    edits = [e for e in plan.record_edits
             if e.elem_id == eid and e.seq == 102 and e.action == "replace"]
    assert edits, "expected a seq-102 replacement record"
    rec = edits[0].new_record
    assert "SR3-2".encode("utf-16-le") in rec
    # decode the framed replacement: 16-byte header, u16 class, object, u32 size
    import struct
    _, _, psize = struct.unpack_from("<qII", rec, 0)
    cls = struct.unpack_from("<H", rec, 16)[0]
    payload = rec[18:16 + psize]
    o = doc.dec.decode_record(cls, payload)
    assert o.clean and o.consumed == o.total
    ent = estorage.entities_in(o.value)[0]
    assert ent["fields"] == {"ASHRAETableName": "SR3-2"}
    # Revit's analytical-model cache still holds the old copy (a derived
    # cache; the ES entity is the source of truth we edited)
    fitting = o.value["m_cellList"]["value"]["m_cells"][2]["value"]["m_oFittingData"]["value"]
    assert fitting["m_ESFieldName"] == "ASHRAETableName"
    assert fitting["m_ESFieldValue"] == "SR3-1"


# ---------------------------------------------------------------------------
# large-file corpus stat (dach: 175 schemas, nested entities/maps/arrays)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_corpus_dach_zero_undecodable():
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE set")
    _need(DACH)
    from rvt.mutate import Document
    from rvt import estorage
    doc = Document.from_file(DACH)
    cat = estorage.schemas(doc)
    assert len(cat) == 175 and cat.map_count == 175
    lar = cat.get("e66bb137-172f-41a5-b680-9aa2dc8bb53f")
    assert lar.name == "LARData"
    assert [(f.name, f.type_name, f.container_type) for f in lar.fields] == [
        ("AnalysisInfo", "ESEntity", 1),
        ("AnalysisInfoPending", "ESEntity", 0),
        ("LARData", "std::pair< AString, AString >", 2),
        ("LevelResults", "std::pair< ElementId, ESEntity >", 2)]
    res = estorage.verify_document(doc, cat)
    assert res.records_examined == 1743
    assert res.undecodable == 0
    assert res.roundtrip_exact == res.records_examined
    assert res.entities > 6000          # top-level + nested entities

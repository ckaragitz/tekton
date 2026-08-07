"""Tests for rvt.families: embedded family-document reconnaissance.

Facts under test (see docs/writer/family-authoring.md):
  * a project's Partitions/<N> save units 1..k are embedded family documents;
    the host ``Family`` element's ``m_oFamDoc.m_contentDocGUID`` == the unit
    separator GUID (rme: 147/159 families resolve; the rest are system /
    in-place families with no document);
  * unit 0 (host) record count == the partition header's elem_table_count;
  * an embedded family document decodes 100% clean and contains the family
    editor element types (self-Family, RefPlane, extrusions, ConnectorElem);
  * an .rfa is the same container + the same Formats/Latest schema, with ONE
    save unit = the family document, plus a PartAtom stream.
"""
import hashlib
import os
import struct
import zlib

import pytest

from rvt.container import open_rvt
from rvt.families import (FamilyIndex, dump_family, family_documents,
                          find_family, self_family_of_unit,
                          content_documents_by_guid, content_document_adoc,
                          encoder_roundtrip, emit_rfa, unit_segments,
                          OST_LightingFixtures, OST_ElectricalEquipment)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RFA_2026 = os.path.join(ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                        "racbasicsamplefamily-2026.rfa")


@pytest.fixture(scope="module")
def rme():
    return FamilyIndex.open("rmebasicsampleproject")


@pytest.fixture(scope="module")
def rme_inventory(rme):
    return family_documents(rme)


# ---------------------------------------------------------------------------
# unit structure
# ---------------------------------------------------------------------------

def test_units_and_host_document(rme):
    # rme: 306 save units = host + 305 embedded documents
    assert len(rme.units) == 306
    assert rme.units[0].guid is None
    assert all(u.guid for u in rme.units[1:])
    # unit 0 == the host document: its record count equals the ElemTable
    # count carried in the partition stream header (28,132); sentinel excluded
    host = rme.unit_records(0)
    assert len(host[101]) == len(host[102]) == len(host[103]) == 28132
    # every embedded unit's separator counter == its element record count
    for u in rme.units[1:20]:
        recs = rme.unit_records(u.index)
        assert len(recs[102]) == u.counter
        assert set(recs[101]) == set(recs[102]) == set(recs[103])


def test_element_ids_unique_across_units(rme):
    seen = set()
    for u in rme.units:
        ids = set(rme.unit_records(u.index).get(102, {}))
        assert not (ids & seen), f"unit {u.index} shares ids with an earlier unit"
        seen |= ids


# ---------------------------------------------------------------------------
# host family -> embedded document linkage
# ---------------------------------------------------------------------------

def test_inventory_resolution(rme_inventory):
    rows = rme_inventory
    assert len(rows) == 159
    resolved = [r for r in rows if r["unit"] is not None]
    assert len(resolved) == 147
    # every resolved family lands on a distinct unit >= 1
    units = [r["unit"] for r in resolved]
    assert len(set(units)) == len(units)
    assert all(u >= 1 for u in units)
    # unresolved ones are system / in-place families without a document
    for r in rows:
        if r["unit"] is None:
            assert r["content_doc_guid"] is None


def test_content_doc_guid_matches_unit_separator(rme, rme_inventory):
    for r in rme_inventory:
        if r["unit"] is None:
            continue
        assert rme.units[r["unit"]].guid == r["content_doc_guid"]


def test_recessed_light_family_row(rme_inventory):
    row = next(r for r in rme_inventory
               if r["family_name"] == "M_Plain Recessed Lighting Fixture")
    assert row["family_id"] == 365618
    assert row["category"] == OST_LightingFixtures
    assert row["unit"] is not None
    assert row["n_types"] == 1
    assert row["n_connectors"] == 1                    # its electrical connector
    assert row["geometry"].get("ExtrusionElem", 0) == 5  # recessed can = extrusions
    assert row["n_ref_planes"] >= 4


def test_panelboard_family_row(rme_inventory):
    row = next(r for r in rme_inventory if r["family_id"] == 454674)
    assert row["category"] == OST_ElectricalEquipment
    assert row["unit"] is not None
    assert row["big2small_count"] > 0        # host->embedded id map present
    assert row["work_plane_based"] is True    # face-hosted equipment family


# ---------------------------------------------------------------------------
# dump of an embedded family document
# ---------------------------------------------------------------------------

def test_dump_recessed_light_decodes_clean(rme):
    row = find_family(rme, "Plain Recessed Lighting Fixture")
    d = dump_family(rme, row["unit"])
    assert d["decode_stats_seq102"]["error_classes"] == {}
    assert d["decode_stats_seq102"]["clean"] == d["decode_stats_seq102"]["records"] > 500
    assert d["decode_stats_seq103"]["error_classes"] == {}
    hist = d["classes_histogram_seq102"]
    for cls in ("Family", "ExtrusionElem", "RefPlane", "ConnectorElem",
                "ParamElemFamily", "VarSketch", "CurveElem", "SketchPlane", "Level"):
        assert hist.get(cls, 0) >= 1, cls
    # extrusion solids carry a real cached GElement rep in seq 103
    assert d["rep_class_by_element_class"]["ExtrusionElem"] == {"GElement": 5}
    # the self family: lighting category, family params, nested annotation fams
    sf = d["self_family"]
    assert sf["category"] == OST_LightingFixtures
    assert sf["n_nested_families"] >= 1
    assert len(sf["family_params"]) >= 30
    ext = d["detail"]["ExtrusionElem"][0]
    assert ext["clean"] is True
    pids = {p["m_paramId"] for p in
            ext["value"]["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
    assert {-1001800, -1001801} <= pids     # extrusion start / end offsets


def test_self_family_is_the_common_famId(rme):
    row = find_family(rme, "Panelboard - 208V MLO")
    sf = self_family_of_unit(rme, row["unit"])
    assert sf["category"] == OST_ElectricalEquipment
    assert sf["work_plane_based"] is True
    # most elements in the family document point m_famId at the self family
    recs = rme.unit_records(row["unit"])[102]
    hits = sum(1 for eid in recs
               if (rme.value(row["unit"], eid) or {}).get("m_famId") == sf["id"])
    assert hits > len(recs) // 3


# ---------------------------------------------------------------------------
# .rfa == same container + same schema, one unit = the family document
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(RFA_2026), reason="rfa sample missing")
def test_rfa_is_same_format():
    with open_rvt(RFA_2026) as f, \
            open_rvt(os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")) as g:
        names = {s.name for s in f.streams()}
        # same Global/* + Formats/Latest layout, plus the family-only PartAtom
        for s in ("Formats/Latest", "Global/Latest", "Global/ElemTable",
                  "Global/ContentDocuments", "Global/History",
                  "Global/PartitionTable", "Global/DocumentIncrementTable",
                  "PartAtom", "BasicFileInfo", "TransmissionData", "Contents"):
            assert s in names
        # byte-identical per-release schema => identical decoder/encoder
        h_rfa = hashlib.sha256(f.inflate("Formats/Latest")).hexdigest()
        h_rvt = hashlib.sha256(g.inflate("Formats/Latest")).hexdigest()
        assert h_rfa == h_rvt
        # PartAtom is plain (unframed) Atom XML
        pa = f.raw("PartAtom")
        assert pa.startswith(b"<?xml") and pa.rstrip().endswith(b"</entry>")
    idx = FamilyIndex.open(RFA_2026)
    assert len(idx.units) == 1                       # the family doc IS unit 0
    st = idx.decode_stats(0)
    assert st["error_classes"] == {} and st["clean"] == st["records"] > 1000
    hist = idx.class_histogram(0)
    assert hist.get("ExtrusionElem", 0) >= 1 and hist.get("Family", 0) >= 1
    # the family's own self-Family element decodes and has a real category
    sf = self_family_of_unit(idx, 0)
    assert sf is not None and (sf["category"] or 0) < 0
    # a standalone .rfa keeps its TYPES inside the document (host-side in a
    # project): the sample table has 4 named types with parameter sets
    assert len(sf["types"]) == 4
    assert {"0762 x 0762mm", "0610 x 0915mm"} <= {t["name"] for t in sf["types"]}


# ---------------------------------------------------------------------------
# ContentDocuments: every embedded document's ADocument is located by GUID
# ---------------------------------------------------------------------------

def test_content_documents_located_by_guid(rme):
    rows = content_documents_by_guid(rme)
    assert len(rows) == 305                          # one per embedded unit
    found = [r for r in rows if r["cd_offset"] is not None]
    assert len(found) == 305                         # 305/305 located
    for r in found:
        assert r["null_lead_pointers"] is True       # a303 -1 a203 -1 lead
        assert r["adoc_class"] == 0x1c               # ADocument class id
    # entries are laid out back-to-back: next entry = adoc_offset + adoc_len + 36
    by_off = sorted(found, key=lambda r: r["cd_offset"])
    gaps = [(b["cd_offset"] - a["cd_offset"]) - a["adoc_len"]
            for a, b in zip(by_off, by_off[1:])]
    assert min(gaps) == max(gaps) == 36
    # the recessed light's entry: its 0x0ae9 slot names its OWN self-Family
    row = find_family(rme, "Plain Recessed Lighting Fixture")
    sf = self_family_of_unit(rme, row["unit"])
    ent = next(r for r in rows if r["unit"] == row["unit"])
    assert ent["self_family_id"] == sf["id"]
    adoc = content_document_adoc(rme, ent["guid"])
    assert adoc is not None and len(adoc) == ent["adoc_len"]
    assert adoc[:2] == b"\x1c\x00"                    # u16 ADocument class lead


# ---------------------------------------------------------------------------
# encoder round-trip + F1/F2 (.rfa full re-emit and type-parameter edit)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(RFA_2026), reason="rfa sample missing")
def test_encoder_roundtrip_rfa_is_byte_identical():
    rt = encoder_roundtrip(RFA_2026, 0)
    assert rt["all_pass"] is True
    for seq in ("101", "102", "103"):
        assert rt[seq]["fail"] == 0 and rt[seq]["skipped_unclean"] == 0
        assert rt[seq]["pass"] == rt[seq]["tested"] == 1993   # 1992 elements + sentinel


def test_encoder_roundtrip_recessed_light_is_byte_identical(rme):
    row = find_family(rme, "Plain Recessed Lighting Fixture")
    rt = encoder_roundtrip(rme, row["unit"])
    assert rt["all_pass"] is True
    assert rt["102"]["fail"] == 0 and rt["102"]["pass"] == 606


@pytest.fixture(scope="module")
def emitted(tmp_path_factory):
    if not os.path.exists(RFA_2026):
        pytest.skip("rfa sample missing")
    d = tmp_path_factory.mktemp("rfa")
    f1 = str(d / "F1.rfa")
    f2 = str(d / "F2.rfa")
    r1 = emit_rfa(RFA_2026, f1)
    r2 = emit_rfa(RFA_2026, f2, edits=[
        {"param_id": 4253, "value": 3.0, "type_name": "0610 x 0160mm"}])
    return {"f1": (f1, r1), "f2": (f2, r2)}


def test_emit_rfa_full_reencode_f1(emitted):
    path, rep = emitted["f1"]
    v = rep["verify"]
    assert v["ok"] is True
    assert v["gzip_crc_failures"] == 0 and v["ecc_mismatch"] == 0
    assert v["walker_errors"] == [] and v["ids_match_source"] is True
    assert v["record_counts"] == {"101": 1993, "102": 1993, "103": 1993}
    st = v["decode_seq102"]
    assert st["clean"] == st["records"] == 1992
    # every record was re-encoded (byte-identically) by the encoder
    for seq in ("101", "102", "103"):
        assert rep["reencode"][seq]["reencoded"] == 1992
        assert rep["reencode"][seq]["identical_to_original"] is True
    # zero semantic change: element records equal the source's exactly
    src = FamilyIndex.open(RFA_2026)
    out = FamilyIndex.open(path)
    assert unit_segments(out, 0) == unit_segments(src, 0)
    # every framed stream carries real CRCIO ECC; unframed streams are copies
    actions = {s["name"]: s["action"] for s in rep["streams"]}
    assert actions["PartAtom"] == "copied" and actions["BasicFileInfo"] == "copied"
    assert "re-encoded" in actions["Partitions/69"]
    with open_rvt(path) as f, open_rvt(RFA_2026) as g:
        assert f.raw("PartAtom") == g.raw("PartAtom")
        # inflated Global payloads are content-identical to the source
        for s in ("Global/Latest", "Global/ElemTable", "Formats/Latest"):
            assert f.inflate(s) == g.inflate(s)


def test_emit_rfa_type_param_edit_f2(emitted):
    path, rep = emitted["f2"]
    assert rep["verify"]["ok"] is True
    (ed,) = rep["edits"]
    assert ed["changed"] == [{"where": "type['0610 x 0160mm']",
                              "old": pytest.approx(2.001312335958005), "new": 3.0}]
    assert ed["new_stamp"] != ed["old_stamp"]
    # the edited value reads back; the record stamp is a valid adler32 stamp
    idx = FamilyIndex.open(path)
    sf = self_family_of_unit(idx, 0)
    v = idx.value(0, sf["id"])
    got = {}
    for pr in v["m_pFamilyTypes"]["value"]["m_pairs"]:
        for p in pr["params"]["m_params"]:
            if p["m_paramId"] == 4253:
                got[pr["name"]] = p["m_value"]
    assert got["0610 x 0160mm"] == pytest.approx(3.0)
    assert got["0762 x 0762mm"] == pytest.approx(2.5)          # untouched
    rec = idx.unit_records(0)[102][sf["id"]]
    calc = zlib.adler32(struct.pack("<H", rec.class_id) + rec.payload) & 0xFFFFFFFF
    assert rec.stamp == calc == ed["new_stamp"]
    # only that one seq-102 record differs from the F1 (unedited) emit
    src = FamilyIndex.open(RFA_2026)
    a, b = unit_segments(idx, 0), unit_segments(src, 0)
    assert a[101] == b[101] and a[103] == b[103] and a[102] != b[102]
    diff = sum(1 for x, y in zip(a[102], b[102]) if x != y)
    assert 0 < diff <= 16                                     # double + stamp

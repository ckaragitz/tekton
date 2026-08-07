"""Tests for tools/latest_map.py - the Global/Latest landmark-region map."""
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import latest_map as lm  # noqa: E402

SAMPLES_DIR = os.path.join(ROOT, "samples")
HAVE_SAMPLES = os.path.exists(
    os.path.join(SAMPLES_DIR, "rstbasicsampleproject.rvt"))


def astr(s: str) -> bytes:
    b = s.encode("utf-16-le")
    return struct.pack("<I", len(b) // 2) + b


def i64(v: int) -> bytes:
    return struct.pack("<q", v)


# --------------------------------------------------------------------------
# primitives / synthetic
# --------------------------------------------------------------------------

def test_astring_at_and_printable():
    d = b"\x00\x00" + astr("Kitchen & Dining")
    assert lm.astring_at(d, 2) == ("Kitchen & Dining", len(d))
    assert lm.astring_at(d, 0) is None or lm.astring_at(d, 0)[0] != "Kitchen"
    assert lm.printable("240 m² - 280 m²")
    assert lm.printable("FOUNDATION-2700")
    assert not lm.printable("一鿿丁")   # CJK garbage from binary
    assert not lm.printable("   ")


def test_classify_string_product_vs_project():
    assert lm.classify_string("Autodesk Revit") == "product"
    assert lm.classify_string("ColorFillSecondaryData") == "product"
    assert lm.classify_string("Rebar Numbering") == "product"
    assert lm.classify_string("Kitchen & Dining") == "project"
    assert lm.classify_string("Rooms : Name") == "project"
    assert lm.classify_string("FOUNDATION-2700") in ("project", "ambiguous")
    assert lm.classify_string("240 m² - 280 m²") == "project"
    assert lm.classify_string("1046264.1.1471776") == "project"


def test_find_json_table_synthetic():
    hdr = i64(802435) + i64(-1) + i64(1) + i64(-1) + struct.pack("<II", 1, 2)
    pairs = (astr("autodesk.unit.unit:meters-1.0.0")
             + astr('{ "typeid": "autodesk.unit.unit:meters-1.0.0" }')
             + astr("autodesk.spec.aec:length-1.0.0")
             + astr('{ "typeid": "autodesk.spec.aec:length-1.0.0" }'))
    d = b"\x00" * 100 + hdr + pairs + b"\x00" * 50
    t = lm.find_json_tables(d)
    assert len(t) == 1
    assert t[0]["count"] == 2 and t[0]["declared"] == 2
    assert t[0]["owner_element_id"] == 802435
    assert t[0]["namespaces"] == {"autodesk.unit.unit": 1,
                                   "autodesk.spec.aec": 1}


def test_id_array_vs_id_map_and_periodic():
    ids = set(range(200, 400))
    # stride-8 id array
    arr = struct.pack("<I", 5) + b"".join(i64(v) for v in (201, 202, 250, 300, 301))
    # id-map: 20-byte records {i64 key(negative), i64 id, u32 flag}
    m = b"".join(i64(-2000011 - k) + i64(210 + k) + struct.pack("<I", 0)
                 for k in range(6))
    d = b"\xaa" * 200 + arr + b"\xaa" * 400 + m + b"\xaa" * 200
    hits = lm.scan_ids(d, ids)
    clusters = lm.merge_periodic(lm.cluster_ids(hits))
    kinds = sorted(lm.classify_id_cluster(c)[0] for c in clusters)
    assert "id-array" in kinds and "id-map" in kinds


def test_merge_periodic_joins_fixed_records():
    ids = set(range(1000, 2000))
    # 141-byte records each holding two ids -> many 2-hit clusters, period 157
    rec = i64(1500) + b"\x00" * 5 + i64(1501) + b"\x33" * 128
    d = b"".join(rec for _ in range(10))
    hits = lm.scan_ids(d, ids)
    plain = lm.cluster_ids(hits)
    merged = lm.merge_periodic(plain)
    assert len(plain) >= 10 and len(merged) == 1
    assert lm.classify_id_cluster(merged[0])[0] == "id-map"


def test_latest_map_coverage_and_kinds_synthetic():
    hdr = i64(7) + i64(-1) + i64(1) + i64(-1) + struct.pack("<II", 1, 2)
    tbl = (hdr + astr("autodesk.unit.unit:feet-1.0.1")
           + astr('{ "typeid": "autodesk.unit.unit:feet-1.0.1" }')
           + astr("autodesk.unit.unit:inches-1.0.1")
           + astr('{ "typeid": "autodesk.unit.unit:inches-1.0.1" }'))
    names = astr("Hall") + astr("Kitchen & Dining") + astr("Laundry")
    payload = b"\x00" * 60 + tbl + b"\x00" * 40 + names + b"\x00" * 60
    regions = lm.latest_map(payload)
    kinds = {r["kind"] for r in regions}
    assert "json-corpus" in kinds and "string-table" in kinds
    # regions tile the payload exactly (no gaps/overlaps)
    body = [r for r in regions if r["end"] <= len(payload)]
    assert body[0]["start"] == 0
    for a, b in zip(body, body[1:]):
        assert a["end"] == b["start"]
    cov = lm.coverage(regions, len(payload))
    assert cov["by_kind"]["json-corpus"] > 0
    assert cov["classified_pct"] > 50


# --------------------------------------------------------------------------
# corpus (needs samples/)
# --------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_SAMPLES, reason="samples not present")
def test_json_corpus_two_tables_identical_across_samples():
    a = lm.load_payload("rstbasicsampleproject")
    b = lm.load_payload("racbasicsampleproject")
    ta, tb = lm.find_json_tables(a), lm.find_json_tables(b)
    assert [t["count"] for t in ta] == [893, 422]
    assert [t["count"] for t in tb] == [893, 422]
    # byte-identical corpus (product data), differing owner element ids
    assert [t["sha256_16"] for t in ta] == [t["sha256_16"] for t in tb]
    assert ta[0]["owner_element_id"] != tb[0]["owner_element_id"]
    assert (ta[0]["end"] - ta[0]["start"]) == 796_206
    assert (ta[1]["end"] - ta[1]["start"]) == 537_134


@pytest.mark.skipif(not HAVE_SAMPLES, reason="samples not present")
def test_map_racbasic_high_coverage():
    d = lm.load_payload("racbasicsampleproject")
    ids = lm.load_elem_ids("racbasicsampleproject")
    regions = lm.latest_map(d, ids)
    cov = lm.coverage(regions, len(d))
    assert cov["classified_pct"] > 90.0
    assert cov["by_kind_pct"]["json-corpus"] > 80.0
    kinds = {r["kind"] for r in regions}
    assert {"json-corpus", "string-table", "id-array", "id-map",
            "object-graph"} <= kinds

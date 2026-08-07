"""Schema-directed object decoding (src/rvt/objects.py) on real corpus data.

Runs against ``racbasicsampleproject`` (needs the extracted corpus and the
canonical schema; skipped cleanly if either is absent).  The heavy element
segment is loaded once per session.

    RVT_SKIP_LARGE=1  -> skip the full-corpus decode tests
"""
from __future__ import annotations

import os
import struct
from collections import Counter, defaultdict

import pytest

from rvt import objects
from rvt.objects import (ObjectDecoder, Reader, DecodeError, iter_records,
                         load_segment, _collect_element_ids)

PROJECT = "racbasicsampleproject"
ROOT = objects.ROOT
SCHEMA_JSON = os.path.join(ROOT, "extracted", "_schema", "schema.json")
PART_DIR = os.path.join(ROOT, "extracted", PROJECT)

pytestmark = pytest.mark.skipif(
    not os.path.exists(SCHEMA_JSON) or not os.path.isdir(PART_DIR),
    reason="extracted corpus / canonical schema not present",
)

skip_large = pytest.mark.skipif(
    os.environ.get("RVT_SKIP_LARGE") == "1", reason="RVT_SKIP_LARGE=1")


# ---------------------------------------------------------------------------
# unit tests: primitive reader + tolerance (no corpus needed beyond schema)
# ---------------------------------------------------------------------------

def test_reader_primitives():
    b = (struct.pack("<i", -7) + struct.pack("<q", 1234567890123) +
         struct.pack("<d", 9.84252) + b"\x03\x00\x00\x00" +
         "abc".encode("utf-16-le") + bytes(range(16)) +
         struct.pack("<3d", 1.0, 2.0, 3.0))
    r = Reader(b)
    assert r.i32() == -7
    assert r.i64() == 1234567890123
    assert abs(r.f64() - 9.84252) < 1e-12
    assert r.astring() == "abc"
    assert r.guid() == "03020100-0504-0706-0809-0a0b0c0d0e0f"
    assert r.xyz() == [1.0, 2.0, 3.0]
    assert r.remaining() == 0


def test_reader_null_astring_and_bounds():
    assert Reader(b"\xff\xff\xff\xff").astring() is None
    with pytest.raises(DecodeError):
        Reader(b"\x10\x00\x00\x00xx").astring()          # length overrun
    with pytest.raises(DecodeError):
        Reader(b"\x00\x00").u32()                          # truncation
    r = Reader(b"\xff\xff\xff\x7f" + b"\x00" * 4)
    with pytest.raises(DecodeError):
        r.count32(4, "count")                              # runaway cap


@pytest.fixture(scope="module")
def decoder():
    return ObjectDecoder()


def test_decoder_tolerates_garbage(decoder):
    """A misparse must produce errors[] and stop, never raise or hang."""
    cid = decoder.schema.by_name["GStyleElem"].type_id
    obj = decoder.decode_record(cid, os.urandom(64))
    assert obj.total == 64
    assert obj.errors or obj.consumed <= obj.total
    if obj.errors:
        e = obj.errors[0]
        assert set(e) >= {"field", "offset", "error"}
    # unknown class id
    bad = decoder.decode_record(0x7FFF, b"\x00" * 8)
    assert bad.errors and not bad.clean


def test_element_id_field_layout(decoder):
    """ElementId value fields flatten to int64; class chain is parent-first."""
    s = decoder.schema
    chain = [c.name for c in decoder.chain(s.by_name["Level"].type_id)]
    assert chain == ["Element", "DatumPlane", "Level"], chain
    # ADocument-independent sanity: Element is the universal root base
    assert decoder.chain(s.by_name["SWall"].type_id)[0].name == "Element"


# ---------------------------------------------------------------------------
# corpus tests (racbasic seq 102)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def seg102():
    cache = os.environ.get("RVT_SEG_CACHE")
    return load_segment(PROJECT, 102, cache)


@pytest.fixture(scope="module")
def records(seg102):
    return [r for r in iter_records(seg102, 102) if r.elem_id >= 0]


@skip_large
def test_record_framing_trailer(seg102):
    """Every record's trailing u32 psize repeat matches (framing proof)."""
    n = ok = 0
    for r in iter_records(seg102, 102):
        n += 1
        ok += r.trailer_ok
    assert n > 50_000
    assert ok == n, f"{n - ok} records with mismatched size trailer"


@skip_large
def test_class_word_identity_mapping(records, decoder):
    """type_id == record class word low u16 (identity); +/-1 collapse."""
    sample = records[:1500]
    res = {}
    for k in (-1, 0, 1):
        clean = 0
        for r in sample:
            cid = r.class_id + k
            if cid in decoder.schema.by_id:
                clean += decoder.decode_record(cid, r.payload).clean
        res[k] = clean / len(sample)
    assert res[0] >= 0.98, res
    assert res[0] > 10 * max(res[-1], res[1], 1e-9), res


@skip_large
def test_class_roundtrip_decode_rate(records, decoder):
    """>=95% of a top class's records must decode 100% of body bytes."""
    counts = Counter(r.class_id for r in records)
    checked = 0
    for cid, _ in counts.most_common(5):
        recs = [r for r in records if r.class_id == cid]
        clean = sum(decoder.decode_record(r.class_id, r.payload).clean for r in recs)
        rate = clean / len(recs)
        assert rate >= 0.95, f"{decoder.class_name(cid)} clean rate {rate:.4f}"
        checked += 1
    assert checked == 5


@skip_large
def test_levels_have_plausible_elevations(records, decoder):
    """Level elements: real names (AString) and plausible plane elevations."""
    lid = decoder.schema.by_name["Level"].type_id
    names, elevs = {}, {}
    for r in records:
        if r.class_id != lid:
            continue
        obj = decoder.decode_record(r.class_id, r.payload)
        assert obj.clean, obj.errors
        v = obj.value
        assert v["m_id"] == r.elem_id            # decoded id == record id
        surf = v.get("m_pSurface")
        assert surf and surf["ptr_class"] == "Plane"
        z = surf["value"]["m_origin"][2]
        assert -500.0 < z < 2000.0, z
        names[r.elem_id] = v["m_text"]
        elevs[r.elem_id] = z
    assert len(names) >= 5
    by_name = defaultdict(list)
    for eid, nm in names.items():
        by_name[nm].append(elevs[eid])
    # the sample project has these storeys (feet)
    assert any(abs(z) < 1e-6 for z in by_name["Level 1"])
    assert any(abs(z - 9.84251968) < 1e-3 for z in by_name["Level 2"]), by_name["Level 2"]
    assert any(abs(z - 19.68503937) < 1e-3 for z in by_name["Roof Line"])
    assert any(z < -1.0 for z in by_name["Foundation"])


@skip_large
def test_wall_location_lines(records, decoder):
    """SWall location curve = GLine with real end params (wall length)."""
    wid = decoder.schema.by_name["SWall"].type_id
    lengths = []
    for r in records:
        if r.class_id != wid:
            continue
        obj = decoder.decode_record(r.class_id, r.payload)
        assert obj.clean, obj.errors
        drv = obj.value.get("m_pCurveDriver")
        assert drv and drv["ptr_class"] == "VWallDriver"
        crv = drv["value"]["m_pCrv"]
        if crv and crv.get("ptr_class") == "GLine":
            p0, p1 = crv["value"]["m_endParams"]
            lengths.append(p1 - p0)
    assert len(lengths) >= 10
    assert all(0.0 < L < 500.0 for L in lengths), lengths
    # racbasic contains 3 m (9.84252 ft) wall segments
    assert any(abs(L - 9.84251968) < 1e-3 for L in lengths)


@skip_large
def test_decoded_element_ids_intersect_elemtable(records, decoder):
    from rvt.elemtable import load_elemtable
    et_ids = set(load_elemtable(PROJECT).ids())
    seen = set()
    for r in records[::17][:3000]:
        obj = decoder.decode_record(r.class_id, r.payload)
        if obj.clean:
            _collect_element_ids(obj.value, seen)
    hit = seen & et_ids
    assert len(hit) >= 200, len(hit)
    # every ElemTable id is a partition record id (elem records exist)
    rec_ids = {r.elem_id for r in records}
    assert len(et_ids & rec_ids) / len(et_ids) > 0.99
